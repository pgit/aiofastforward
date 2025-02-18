import asyncio
import unittest
from threading import (
    Thread,
)
from unittest import (
    TestCase,
)
from unittest.mock import (
    Mock,
    call,
    patch,
)

import aiofastforward


def async_test(func):
    def wrapper(*args, **kwargs):
        future = func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper


class TestCallLater(TestCase):

    @async_test
    async def test_concurrent_called_in_order(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            loop.call_later(1, callback, 0)
            loop.call_later(1, callback, 1)

            forward(1)
            self.assertEqual(callback.mock_calls, [call(0), call(1)])

    @async_test
    async def test_is_cumulative_no_await(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            loop.call_later(1, callback, 0)
            loop.call_later(2, callback, 1)

            forward(1)
            self.assertEqual(callback.mock_calls, [call(0)])
            forward(1)
            self.assertEqual(callback.mock_calls, [call(0), call(1)])

    @async_test
    async def test_is_cumulative_with_await(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            loop.call_later(1, callback, 0)
            loop.call_later(2, callback, 1)

            await forward(1)
            self.assertEqual(callback.mock_calls, [call(0)])
            await forward(1)
            self.assertEqual(callback.mock_calls, [call(0), call(1)])

    @async_test
    async def test_correct_order(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            loop.call_later(2, callback, 0)
            loop.call_later(1, callback, 1)

            forward(1)
            self.assertEqual(callback.mock_calls, [call(1)])
            forward(1)
            self.assertEqual(callback.mock_calls, [call(1), call(0)])

    @async_test
    async def test_zero_correct_order(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            loop.call_later(0, callback, 0)

            self.assertEqual(callback.mock_calls, [])
            forward(0)
            self.assertEqual(callback.mock_calls, [call(0)])

    @async_test
    async def test_callback_called_if_after_forward(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            called = asyncio.Event()

            self.assertFalse(called.is_set())
            forward(1)
            loop.call_later(1, called.set)
            await called.wait()

    @async_test
    async def test_can_be_cancelled(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            handle = loop.call_later(1, callback, 0)

            self.assertEqual(handle._cancelled, False)
            handle.cancel()
            self.assertEqual(handle._cancelled, True)

            await forward(1)
            self.assertEqual(callback.mock_calls, [])

    @async_test
    async def test_handle_is_timerhandle(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            handle = loop.call_later(1, callback, 0)
            self.assertTrue(isinstance(handle, asyncio.TimerHandle))

    @async_test
    async def test_original_restored_on_exception(self):

        loop = asyncio.get_event_loop()
        original_call_later = loop.call_later
        try:
            with aiofastforward.FastForward(loop):
                raise Exception()
        except BaseException:
            pass

        self.assertEqual(loop.call_later, original_call_later)


class TestCallAt(TestCase):

    @async_test
    async def test_concurrent_called_in_order(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            now = loop.time()
            loop.call_at(now + 1, callback, 0)
            loop.call_at(now + 1, callback, 1)

            forward(1)
            self.assertEqual(callback.mock_calls, [call(0), call(1)])

    @async_test
    async def test_is_cumulative(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            now = loop.time()
            loop.call_at(now + 1, callback, 0)
            loop.call_at(now + 2, callback, 1)

            forward(1)
            self.assertEqual(callback.mock_calls, [call(0)])
            forward(1)
            self.assertEqual(callback.mock_calls, [call(0), call(1)])

    @async_test
    async def test_short_forward_not_trigger_callback(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            now = loop.time()
            loop.call_at(now + 2, callback, 0)

            forward(1)
            self.assertEqual(callback.mock_calls, [])
            forward(1)
            self.assertEqual(callback.mock_calls, [call(0)])

    @async_test
    async def test_original_restored_on_exception(self):

        loop = asyncio.get_event_loop()
        original_call_at = loop.call_at
        try:
            with aiofastforward.FastForward(loop):
                raise Exception()
        except BaseException:
            pass

        self.assertEqual(loop.call_at, original_call_at)


class TestTime(TestCase):

    @async_test
    async def test_time_is_float(self):

        loop = asyncio.get_event_loop()

        with aiofastforward.FastForward(loop) as forward:
            self.assertTrue(isinstance(loop.time(), float))
            forward(1)
            self.assertTrue(isinstance(loop.time(), float))

    @async_test
    async def test_forward_moves_time_forward_after_sleep_resolves(self):

        loop = asyncio.get_event_loop()

        async def sleeper_a():
            await asyncio.sleep(1)

        async def sleeper_b():
            await asyncio.sleep(2)

        with aiofastforward.FastForward(loop) as forward:
            time_a = loop.time()
            forward(1)
            time_b = loop.time()
            forward(2)
            time_c = loop.time()

            self.assertEqual(time_b, time_a)
            self.assertEqual(time_c, time_a)

            await asyncio.ensure_future(sleeper_a())
            self.assertEqual(loop.time(), 1)
            await asyncio.ensure_future(sleeper_b())
            self.assertEqual(loop.time(), 3)

    @async_test
    async def test_forward_moves_time_forward_after_forward_awaited(self):

        loop = asyncio.get_event_loop()

        async def sleeper_a():
            await asyncio.sleep(1)

        async def sleeper_b():
            await asyncio.sleep(2)

        with aiofastforward.FastForward(loop) as forward:
            time_a = loop.time()
            forward_1 = forward(1)
            time_b = loop.time()
            forward_3 = forward(2)
            time_c = loop.time()

            self.assertEqual(time_b, time_a)
            self.assertEqual(time_c, time_a)

            task_a = asyncio.ensure_future(sleeper_a())
            await forward_1
            self.assertEqual(loop.time(), 1)
            task_b = asyncio.ensure_future(sleeper_b())
            await forward_3
            self.assertEqual(loop.time(), 3)

            task_a.cancel()
            task_b.cancel()

    @async_test
    async def test_forward_moves_time_forward_after_each_await_even_if_no_exact_callback(self):

        loop = asyncio.get_event_loop()

        async def sleeper():
            await asyncio.sleep(3)

        with aiofastforward.FastForward(loop) as forward:
            time_a = loop.time()

            task = asyncio.ensure_future(sleeper())
            await forward(1)
            self.assertEqual(loop.time(), time_a + 1)
            await forward(1)
            self.assertEqual(loop.time(), time_a + 2)

            task.cancel()

    @async_test
    async def test_original_restored_on_exception(self):

        loop = asyncio.get_event_loop()
        original_time = loop.time
        try:
            with aiofastforward.FastForward(loop):
                raise Exception()
        except BaseException:
            pass

        self.assertEqual(loop.time, original_time)


class TestSleep(TestCase):

    @async_test
    async def test_is_cumulative(self):

        loop = asyncio.get_event_loop()
        at_0 = asyncio.Event()
        at_1 = asyncio.Event()
        at_3 = asyncio.Event()

        async def sleeper():
            at_0.set()
            await asyncio.sleep(1)
            at_1.set()
            await asyncio.sleep(2)
            at_3.set()

        with aiofastforward.FastForward(loop) as forward:

            task = asyncio.ensure_future(sleeper())

            forward(0)
            await at_0.wait()

            forward(0)
            self.assertFalse(at_1.is_set())

            forward(1)
            await at_1.wait()

            forward(1)
            self.assertFalse(at_3.is_set())

            forward(1)
            await at_3.wait()

            task.cancel()

    @async_test
    async def test_gather(self):
        
        loop = asyncio.get_event_loop()
        at_1 = asyncio.Event()
        at_2 = asyncio.Event()

        async def nested_sleeper():
            await asyncio.sleep(1)

        async def interval_sleeper():
            await nested_sleeper()
            at_1.set()
            await asyncio.gather(
                asyncio.ensure_future(nested_sleeper()),
                asyncio.ensure_future(nested_sleeper()),
                asyncio.ensure_future(nested_sleeper())
            )
            at_2.set()

        async def long_sleeper():
            await asyncio.sleep(3)

        with aiofastforward.FastForward(loop) as forward:
            tasks = [
                asyncio.ensure_future(interval_sleeper()),
                asyncio.ensure_future(long_sleeper()),
            ]

            forward(1)
            await at_1.wait()
            self.assertFalse(at_2.is_set())
            forward(0.5)
            self.assertFalse(at_2.is_set())
            forward(0.5)
            await at_2.wait()

            for task in tasks: task.cancel()

    @async_test
    async def test_sleep_can_resolve_after_yield(self):

        loop = asyncio.get_event_loop()
        at_0 = asyncio.Event()
        at_1 = asyncio.Event()

        async def sleeper():
            await at_0.wait()
            await asyncio.sleep(1)
            at_1.set()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            task = asyncio.ensure_future(sleeper())

            at_0.set()
            forward(0)
            self.assertFalse(at_1.is_set())

            forward(1)
            await at_1.wait()

            task.cancel()

    @async_test
    async def test_out_of_order_forward_sleep_can_resolve_after_yield(self):

        loop = asyncio.get_event_loop()
        at_0 = asyncio.Event()
        at_1 = asyncio.Event()

        async def sleeper():
            await at_0.wait()
            await asyncio.sleep(1)
            at_1.set()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            task = asyncio.ensure_future(sleeper())

            forward(1)
            at_0.set()
            self.assertFalse(at_1.is_set())
            await at_1.wait()

            task.cancel()

    @async_test
    async def test_awaiting_forward_blocks_until_time_in_one_call(self):

        loop = asyncio.get_event_loop()
        at_2 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(1)
            at_2.set()
            await asyncio.sleep(1)

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            asyncio.ensure_future(sleeper())

            await forward(2)
            self.assertTrue(at_2.is_set())

    @async_test
    async def test_awaiting_forward_blocks_until_time_cumulative(self):

        loop = asyncio.get_event_loop()
        at_2 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(1)
            at_2.set()
            await asyncio.sleep(1)

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            task = asyncio.ensure_future(sleeper())

            await forward(0.2)
            self.assertFalse(at_2.is_set())
            await forward(0.2)
            self.assertFalse(at_2.is_set())
            await forward(0.2)
            self.assertFalse(at_2.is_set())
            await forward(0.2)
            self.assertFalse(at_2.is_set())
            await forward(0.2)
            await at_2.wait()

            task.cancel()

    @async_test
    async def test_forward_not_blocks_until_await_and_is_cumulative(self):

        loop = asyncio.get_event_loop()
        at_2 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(1)
            at_2.set()
            await asyncio.sleep(1)

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            task = asyncio.ensure_future(sleeper())

            forward(0.2)
            self.assertFalse(at_2.is_set())
            forward(0.2)
            self.assertFalse(at_2.is_set())
            forward(0.2)
            self.assertFalse(at_2.is_set())
            forward(0.2)
            self.assertFalse(at_2.is_set())
            await forward(0.2)
            await at_2.wait()

            task.cancel()

    @async_test
    async def test_awaiting_forward_blocks_until_time_just_after_sleep(self):

        loop = asyncio.get_event_loop()
        at_2 = asyncio.Event()
        at_3 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(1)
            at_2.set()
            await asyncio.sleep(1)
            at_3.set()

        with aiofastforward.FastForward(loop) as forward:
            callback = Mock()
            task = asyncio.ensure_future(sleeper())

            await forward(1.5)
            self.assertTrue(at_2.is_set())
            self.assertFalse(at_3.is_set())
            task.cancel()

    @async_test
    async def test_one_call_can_resolve_multiple_sleeps(self):

        loop = asyncio.get_event_loop()
        at_3 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(1)
            await asyncio.sleep(2)
            at_3.set()

        with aiofastforward.FastForward(loop) as forward:
            task = asyncio.ensure_future(sleeper())

            forward(3)
            await at_3.wait()

            task.cancel()

    @async_test
    async def test_cancellation(self):

        loop = asyncio.get_event_loop()
        running = asyncio.Event()
        cancelled = asyncio.Event()

        async def sleeper():
            try:
                running.set()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                cancelled.set()

        with aiofastforward.FastForward(loop) as forward:
            task = asyncio.ensure_future(sleeper())

            forward(0)
            await running.wait()

            task.cancel()

            forward(1)
            await cancelled.wait()

    @async_test
    async def test_multiple_calls_can_resolve_multiple_sleeps_no_await(self):

        loop = asyncio.get_event_loop()
        at_4 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(3)
            await asyncio.sleep(1)
            at_4.set()

        with aiofastforward.FastForward(loop) as forward:
            task = asyncio.ensure_future(sleeper())

            forward(2)
            self.assertFalse(at_4.is_set())
            forward(2)
            await at_4.wait()

            task.cancel()

    @async_test
    async def test_multiple_calls_can_resolve_multiple_sleeps_with_await(self):

        loop = asyncio.get_event_loop()
        at_4 = asyncio.Event()

        async def sleeper():
            await asyncio.sleep(3)
            await asyncio.sleep(1)
            at_4.set()

        with aiofastforward.FastForward(loop) as forward:
            task = asyncio.ensure_future(sleeper())

            await forward(2)
            self.assertFalse(at_4.is_set())
            await forward(2)
            await at_4.wait()

            task.cancel()

    @async_test
    async def test_returns_result(self):

        loop = asyncio.get_event_loop()
        result = asyncio.Future()

        async def sleeper():
            value = await asyncio.sleep(1, result='value')
            result.set_result(value)

        with aiofastforward.FastForward(loop) as forward:
            task = asyncio.ensure_future(sleeper())

            forward(1)
            self.assertEqual(await result, 'value')

            task.cancel()

    @async_test
    async def test_original_restored_on_exception(self):

        loop = asyncio.get_event_loop()
        original_sleep = asyncio.sleep
        try:
            with aiofastforward.FastForward(loop):
                raise Exception()
        except BaseException:
            pass

        self.assertEqual(asyncio.sleep, original_sleep)

    @async_test
    async def test_only_patches_specified_loop(self):

        loop = asyncio.get_event_loop()

        sleep_call = None
        async def dummy_sleep(_sleep_call, result=None):
            nonlocal sleep_call
            sleep_call = _sleep_call

        original_sleep = asyncio.sleep
        asyncio.sleep = dummy_sleep

        def run_sleep():
            other_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(other_loop)
            other_loop.run_until_complete(asyncio.sleep(1))

        try:
            with aiofastforward.FastForward(loop) as forward:
                thread = Thread(target=run_sleep)
                thread.start()

                # This does block the event loop in the test, but briefly
                thread.join()

                self.assertEqual(sleep_call, 1)
        finally:
            asyncio.sleep = original_sleep


# contextvars introduced in Python 3.7
try:
    import contextvars
except ImportError:
    contextvars = None

if contextvars:
    context_var = contextvars.ContextVar('var')

    class TestCallLaterContext(TestCase):

        @async_test
        async def test_if_context_not_passed_copy_of_current_context_used(self):

            loop = asyncio.get_event_loop()

            context_var_callback_value = None
            def callback():
                nonlocal context_var_callback_value
                context_var_callback_value = context_var.get()
                context_var.set('callback-value')

            with aiofastforward.FastForward(loop) as forward:
                context_var.set('initial-value')
                loop.call_later(1, callback)

                forward(1)

                self.assertEqual(context_var_callback_value, 'initial-value')
                self.assertEqual(context_var.get(), 'initial-value')

        @async_test
        async def test_if_context_passed_is_used(self):

            loop = asyncio.get_event_loop()

            context_var_callback_value = None
            def callback():
                nonlocal context_var_callback_value
                context_var_callback_value = context_var.get()
                context_var.set('callback-value')

            with aiofastforward.FastForward(loop) as forward:
                context_var.set('initial-value')
                context = contextvars.copy_context()
                context_var.set('modified-value')
                loop.call_later(1, callback, context=context)

                forward(1)

                self.assertEqual(context_var_callback_value, 'initial-value')
                self.assertEqual(context_var.get(), 'modified-value')


    class TestCallAtContext(TestCase):

        @async_test
        async def test_if_context_not_passed_copy_of_current_context_used(self):

            loop = asyncio.get_event_loop()

            context_var_callback_value = None
            def callback():
                nonlocal context_var_callback_value
                context_var_callback_value = context_var.get()
                context_var.set('callback-value')

            with aiofastforward.FastForward(loop) as forward:
                context_var.set('initial-value')
                now = loop.time()
                loop.call_at(now + 1, callback)

                forward(1)

                self.assertEqual(context_var_callback_value, 'initial-value')
                self.assertEqual(context_var.get(), 'initial-value')

        @async_test
        async def test_if_context_passed_is_used(self):

            loop = asyncio.get_event_loop()

            context_var_callback_value = None
            def callback():
                nonlocal context_var_callback_value
                context_var_callback_value = context_var.get()
                context_var.set('callback-value')

            with aiofastforward.FastForward(loop) as forward:
                context_var.set('initial-value')
                context = contextvars.copy_context()
                context_var.set('modified-value')
                now = loop.time()
                loop.call_at(now + 1, callback, context=context)

                forward(1)

                self.assertEqual(context_var_callback_value, 'initial-value')
                self.assertEqual(context_var.get(), 'modified-value')
