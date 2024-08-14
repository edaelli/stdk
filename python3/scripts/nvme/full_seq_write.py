import sys
import argparse
import time
import datetime
import asyncio
import logging
from types import SimpleNamespace

# Import lone libraries that we use below
from lone.nvme.device import NVMeDevice
from lone.system import DMADirection
from lone.nvme.spec.commands.nvm.write import Write
from lone.nvme.spec.prp import PRP
from lone.nvme.spec.commands.status_codes import status_codes
from lone.nvme.spec.commands.admin.format_nvm import FormatNVM


# Logging setup
logger = logging.getLogger('full_seq_write')
formatter = '[%(asctime)s]  %(name)16s %(levelname)8s - %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=formatter)


def initialize_device(pci_slot, queue_depth):

    # Just use a default number for ASQ, ACQ
    asq_depth = 256
    acq_depth = 256

    # To maintain a purely sequential workload to the drive at a queue depth > 1,
    #  we have to limit our number of IO queues to 1. Otherwise the drive will
    # pick the next command to work on from any of the queues, and we can get out
    # of sync
    num_io_queues = 1

    # Since we know our max queue depth, we only need that much in the single
    #  sub/compl queue pair
    io_queue_depth = queue_depth + 1

    # Create a NVMeDevice object for the slot we want to work with
    nvme_device = NVMeDevice(pci_slot)

    # Disable, create queues, get identify information
    nvme_device.cc_disable()
    nvme_device.init_admin_queues(asq_entries=asq_depth, acq_entries=acq_depth)
    nvme_device.cc_enable()
    nvme_device.init_msix_interrupts(num_io_queues + 1, 0)
    nvme_device.create_io_queues(num_io_queues, io_queue_depth)
    nvme_device.identify()

    # Return the nvme_device to the caller
    return nvme_device


def format_device(nvme_device, namespace, fmt_blk_size, timeout_s=60):
    logger.info('Formatting ns {} block_size {}'.format(namespace, fmt_blk_size))

    # Refresh identify data
    nvme_device.identify()

    # Make sure the requested namespace exists
    assert nvme_device.namespaces[namespace] is not None, 'Invalid namespace'

    # Get namespace data
    test_ns = nvme_device.namespaces[namespace]
    test_nsid = test_ns.NSID

    # Find the format LBAF that matches fmt_blk_size
    for i, f in enumerate(test_ns.id_ns_data.LBAF_TBL):
        if (2 ** f.LBADS) == fmt_blk_size:
            test_lbaf = i
            break
    else:
        assert False, 'Did not find the lba format for {}'.format(fmt_blk_size)

    # Format namespace using requested test_lbaf
    fmt_cmd = FormatNVM(NSID=test_nsid, LBAFL=test_lbaf)
    nvme_device.sync_cmd(fmt_cmd, timeout_s=timeout_s)


def create_write_commands(nvme_device, num_cmds, namespace, cmd_xfer_len, nlb):

    # Allocate write commands and PRPs for the queue depth we are maintaining
    wr_cmds = []
    for idx in range(num_cmds):

        # Make a PRP object for each of the write commands
        prp = PRP(cmd_xfer_len, nvme_device.mps)
        prp.alloc(nvme_device, DMADirection.HOST_TO_DEVICE)

        # Make a Write command object with common values
        write_cmd = Write(NSID=namespace, NLB=nlb)

        data_out = bytes([0xED] * cmd_xfer_len)
        prp.set_data_buffer(data_out)

        # Fill in the PRP for the command
        write_cmd.DPTR.PRP.PRP1 = prp.prp1
        write_cmd.DPTR.PRP.PRP2 = prp.prp2

        # Add it to the command list
        wr_cmds.append(write_cmd)

    return wr_cmds


async def print_stats(period_s, statistics, wr_cmds):

    last_completed_cmds = 0
    last_printed_time = time.time()

    while True:
        try:
            await asyncio.sleep(period_s)

            async with asyncio.Lock():
                completed_cmds = statistics.completed_cmds - last_completed_cmds

                logger.info('-' * 80)
                logger.info('Elapsed: {}'.format(datetime.timedelta(
                                                 seconds=time.time() - statistics.start_time)))
                logger.info('Last written LBA: 0x{:08x} (NSZE: 0x{:08x}) {:.02f}%'.format(
                    statistics.last_written_lba,
                    statistics.nsze,
                    (statistics.last_written_lba / statistics.nsze) * 100))
                wr_bw = ((completed_cmds * statistics.cmd_xfer_len) /
                         (time.time() - last_printed_time))
                logger.info('Write IOPs: {:.02f}'.format(
                            completed_cmds / (time.time() - last_printed_time)))
                logger.info('Write BW: {:.02f} MB/s'.format(wr_bw / 1000000))
                if wr_bw > 0:
                    bytes_remaining = ((statistics.nsze - statistics.last_written_lba) *
                                       statistics.lba_ds_bytes)
                    logger.info('ETA: {}'.format(datetime.timedelta(
                                                 seconds=bytes_remaining / wr_bw)))
                logger.info('-' * 80)
                last_completed_cmds = statistics.completed_cmds
            last_printed_time = time.time()

            # Check for command timeouts
            wr_cmd_timeout_s = 5
            outstanding_cmds = [cmd for cmd in wr_cmds if (cmd.posted is True and
                                                           cmd.complete is False)]

            # Check how long they've been with the drive, and assert if > wr_cmd_timeout_s
            wr_cmd_to = False
            time_now = time.perf_counter_ns()
            for wr_cmd in outstanding_cmds:
                cmd_time_s = (time_now - wr_cmd.start_time_ns) / 1000000000

                if cmd_time_s > wr_cmd_timeout_s:
                    logger.info('write cmd SLBA: 0x{:02x} timed out'.format(wr_cmd.SLBA))
                    wr_cmd_to = True

            if wr_cmd_to:
                logger.info('One or more commands timed out, exiting!!')
                # Ask all tasks to exit gracefully
                for t in asyncio.all_tasks():
                    if t.get_name() in ['seq_write', 'complete_commands']:
                        t.cancel()
                        break

        except asyncio.CancelledError:
            # logger.info('print_stats was cancelled, exiting')
            break


async def seq_write(nvme_device, wr_cmds, slba, nsze, statistics):

    # Increment the SLBA squentially
    lba = slba
    last_lba_started = False
    failure = False

    # Keep sending writes to the drive until we have sent the last one
    while True:
        try:
            # Post all available commands
            started_cmds = 0
            for wr_cmd in [cmd for cmd in wr_cmds if (cmd.posted is False and
                                                      cmd.complete is False)]:
                # Stop sending commands at nsze - nlb
                if (lba + wr_cmd.NLB + 1) <= nsze:
                    wr_cmd.SLBA = lba
                    nvme_device.start_cmd(wr_cmd, alloc_mem=False)
                    started_cmds += 1
                    lba += (wr_cmd.NLB + 1)
                else:
                    last_lba_started = True
                    break

            # Complete all commands that are wating for completion
            nvme_device.process_completions()

            # Check status of all completed commands
            for wr_cmd in [cmd for cmd in wr_cmds if (cmd.posted is False and
                                                      cmd.complete is True)]:
                status_codes.check(wr_cmd)

                # Mark this write command as not complete anymore since we will reuse it
                wr_cmd.complete = False

                # Update statistics
                async with asyncio.Lock():
                    statistics.completed_cmds += 1
                    statistics.last_written_lba = wr_cmd.SLBA

            # If we have started the last LBA, and didnt start anything last round, we are done!
            if last_lba_started and started_cmds == 0:
                break

            # Yield to allow other threads to run
            await asyncio.sleep(0)

        except asyncio.CancelledError:
            failure = True

    for t in asyncio.all_tasks():
        if t.get_name() in ['print_stats', 'complete_commands']:
            t.cancel()

    if not failure:
        logger.info('Drive sequential write complete!')
    else:
        raise Exception('Failure')


async def full_seq_write(args):
    # Initialize our device
    nvme_device = initialize_device(args.pci_slot, args.queue_depth)

    # Make sure the requested namespace exists
    assert nvme_device.namespaces[args.namespace] is not None, 'Invalid namespace'

    # Format namespace if requested
    if args.format:
        format_device(nvme_device, args.namespace, args.fmt_blk_size)

    # Calculate some of the namespace's information
    namespace = nvme_device.namespaces[args.namespace]
    ns_block_size = namespace.lba_ds_bytes
    cmd_xfer_len = args.wr_block_size
    cmd_num_blocks = cmd_xfer_len // ns_block_size
    cmd_nlb = cmd_num_blocks - 1

    # Create queue_depth write commands to use in this test
    wr_cmds = create_write_commands(nvme_device,
                                    args.queue_depth,
                                    args.namespace,
                                    cmd_xfer_len,
                                    cmd_nlb)

    # Keep track of statistics to print out as the test runs
    statistics = SimpleNamespace(start_time=time.time(),
                                 cmd_xfer_len=cmd_xfer_len,
                                 completed_cmds=0,
                                 nsze=namespace.nsze,
                                 last_written_lba=args.slba,
                                 lba_ds_bytes=namespace.lba_ds_bytes)

    # Co-routine to print statistics every 5s
    print_stats_task = asyncio.create_task(print_stats(5, statistics, wr_cmds))
    print_stats_task.set_name('print_stats')

    # Co-routine to sequentially write drive
    write_seq = asyncio.create_task(seq_write(nvme_device,
                                              wr_cmds,
                                              args.slba,
                                              namespace.nsze,
                                              statistics))
    write_seq.set_name('seq_write')

    # Log that we are starting
    logger.info(
        'Starting drive fill, drive has {} LBAs ({} bytes/LBA)'.format(namespace.nsze,
                                                                       namespace.lba_ds_bytes))

    # Ok, now wait for it all to complete!
    task = asyncio.current_task()
    task.set_name('main')
    await asyncio.wait_for(asyncio.gather(print_stats_task,
                                          write_seq),
                           args.timeout_s)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    parser.add_argument('namespace', type=int)
    parser.add_argument('--format', action='store_true', default=False)
    parser.add_argument('--fmt-blk-size', type=int, default=4096)
    parser.add_argument('--queue-depth', type=int, default=32)
    parser.add_argument('--wr-block-size', type=int, default=32 * 1024)
    parser.add_argument('--slba', type=int, default=0)
    parser.add_argument('--timeout_s', type=int, default=48 * 60 * 60)
    args = parser.parse_args()

    return asyncio.run(full_seq_write(args))


if __name__ == '__main__':
    sys.exit(main())
