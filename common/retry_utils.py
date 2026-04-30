"""
异常类型定向重试工具 - 仅对指定类型的异常进行重试
避免对业务逻辑失败（如断言不通过）进行无意义的重试
"""
import functools
import time
from typing import Any, Callable, List, Optional, Tuple, Type

# 定义需要重试的异常类型
RETRY_EXCEPTIONS = (
    # Playwright 超时和元素未找到异常
    Exception,  # 临时使用通用异常，实际应根据 Playwright 版本调整
)

# 尝试导入 Playwright 特定异常
try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import Error as PlaywrightError

    RETRY_EXCEPTIONS = (
        PlaywrightTimeoutError,
        PlaywrightError,
        # 网络相关异常
        ConnectionError,
        TimeoutError,
    )
except ImportError:
    pass


def retry_on_exceptions(
    max_retries: int = 2,
    delay: float = 1.0,
    retry_exceptions: Tuple[Type[Exception], ...] = RETRY_EXCEPTIONS,
    logger: Callable = print,
) -> Callable:
    """
    异常类型定向重试装饰器

    :param max_retries: 最大重试次数
    :param delay: 重试间隔（秒）
    :param retry_exceptions: 需要重试的异常类型元组
    :param logger: 日志记录函数
    :return: 装饰后的函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = float(delay)

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger(f"❌ 尝试 {attempt + 1} 失败: {type(e).__name__}: {e}")
                        logger(f"🔄 等待 {current_delay} 秒后重试...")
                        time.sleep(current_delay)
                        current_delay *= 1.5  # 指数退避（不修改装饰器参数 delay）
                    else:
                        logger(f"❌ 所有 {max_retries + 1} 次尝试均失败")
                except Exception as e:
                    # 非重试异常直接抛出
                    logger(f"❌ 非重试异常: {type(e).__name__}: {e}")
                    raise

            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def flaky_test(max_retries: int = 2, delay: float = 1.0) -> Callable:
    """
    标记为 flaky 的测试用例重试装饰器
    专门用于标记为不稳定的测试用例

    :param max_retries: 最大重试次数
    :param delay: 重试间隔（秒）
    :return: 装饰后的函数
    """
    return retry_on_exceptions(
        max_retries=max_retries,
        delay=delay,
        logger=lambda msg: print(f"[Flaky Test] {msg}")
    )


class RetryContext:
    """
    重试工具。支持两种用法：

    1. 推荐 — run() 方法自动重试：
        ctx = RetryContext(max_retries=2)
        ctx.run(lambda: risky_op())

    2. 手动循环（with 块本身不会重进，只压制一次匹配异常）：
        ctx = RetryContext(max_retries=2)
        for _ in range(ctx.max_retries + 1):
            with ctx:
                risky_op()
                break
    """
    def __init__(
        self,
        max_retries: int = 2,
        delay: float = 1.0,
        retry_exceptions: Tuple[Type[Exception], ...] = RETRY_EXCEPTIONS,
        logger: Callable = print,
    ):
        self.max_retries = max_retries
        self._initial_delay = float(delay)
        self.retry_exceptions = retry_exceptions
        self._logger = logger
        self.attempt = 0
        self._current_delay = self._initial_delay

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 仅压制可重试异常；重进 with 块需要调用方在外层套循环
        if exc_type and issubclass(exc_type, self.retry_exceptions):
            if self.attempt < self.max_retries:
                self.attempt += 1
                time.sleep(self._current_delay)
                self._current_delay *= 1.5
                return True
        return False

    def run(self, func: Callable, *args, **kwargs) -> Any:
        """真正的重试：自动循环调用 func，直到成功或耗尽次数。"""
        self.attempt = 0
        self._current_delay = self._initial_delay
        last_exception: Optional[Exception] = None

        for _ in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self.retry_exceptions as e:
                last_exception = e
                if self.attempt < self.max_retries:
                    self._logger(f"尝试 {self.attempt + 1} 失败: {type(e).__name__}: {e}")
                    self._logger(f"等待 {self._current_delay:.1f}s 后重试...")
                    time.sleep(self._current_delay)
                    self._current_delay *= 1.5
                    self.attempt += 1
                else:
                    self._logger(f"所有 {self.max_retries + 1} 次尝试均失败")
                    raise
            except Exception:
                raise

        if last_exception:
            raise last_exception


def should_retry(exception: Exception) -> bool:
    """
    检查异常是否应该重试的辅助函数

    :param exception: 捕获到的异常
    :return: 是否应该重试
    """
    # 检查异常类型是否匹配
    if isinstance(exception, RETRY_EXCEPTIONS):
        return True

    # 检查异常消息是否包含特定模式（用于处理没有明确异常类型的情况）
    error_patterns = [
        "Timeout",
        "timeout",
        "Element not found",
        "element not found",
        "Network error",
        "network error",
        "Connection refused",
        "connection refused",
        "Failed to load",
        "failed to load",
    ]

    exception_str = str(exception)
    for pattern in error_patterns:
        if pattern in exception_str:
            return True

    return False
