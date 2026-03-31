"""
异常类型定向重试工具 - 仅对指定类型的异常进行重试
避免对业务逻辑失败（如断言不通过）进行无意义的重试
"""
import functools
import time
from typing import Callable, Type, List, Tuple, Any

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

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger(f"❌ 尝试 {attempt + 1} 失败: {type(e).__name__}: {e}")
                        logger(f"🔄 等待 {delay} 秒后重试...")
                        time.sleep(delay)
                        delay *= 1.5  # 指数退避
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
    上下文管理器形式的重试工具
    用于非装饰器场景的重试控制
    """
    def __init__(
        self,
        max_retries: int = 2,
        delay: float = 1.0,
        retry_exceptions: Tuple[Type[Exception], ...] = RETRY_EXCEPTIONS,
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.retry_exceptions = retry_exceptions
        self.attempt = 0

    def __enter__(self):
        self.attempt = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, self.retry_exceptions):
            if self.attempt < self.max_retries:
                self.attempt += 1
                time.sleep(self.delay)
                self.delay *= 1.5
                return True  # 继续执行
        return False


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
