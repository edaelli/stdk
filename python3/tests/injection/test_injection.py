import pytest

from lone.injection import Injector, Injection


def test_injector():
    i = Injector()

    # Test no ack path with assertion
    with pytest.raises(AssertionError):
        i.wait(0.01)

    # Pretendit acked, test path
    i.ack = True
    i.wait(0.01)


def test_injection():
    injection = Injection()

    class InjectorTest(Injector):
        pass

    i = InjectorTest()

    # Test we can register an injector
    injection.register(i)

    # Test we can retrieve it
    g_i = injection.get('InjectorTest')
    assert i == g_i

    # Test getting an unregistered injector returns None
    assert injection.get('NotRegistered') is None
