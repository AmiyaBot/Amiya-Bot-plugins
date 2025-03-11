
import time

class QuotaController:

    def __init__(self, logger, plugin):
        self.logger = logger
        self.plugin = plugin
        self.query_times = []

    def debug_log(self, msg):
        show_log = self.plugin.get_config("show_log")
        if show_log == True:
            self.logger.info(f'{msg}')

    def check(self, query_per_hour,  peek: bool = False) -> int:

            if query_per_hour is None or query_per_hour <= 0:
                return 100000

            current_time = time.time()
            hour_ago = current_time - 3600  # 3600秒代表一小时

            # 移除一小时前的查询记录
            self.query_times = [t for t in self.query_times if t > hour_ago]

            current_query_times = len(self.query_times)

            if current_query_times < query_per_hour:
                # 如果过去一小时内的查询次数小于限制，则允许查询
                if not peek:
                    self.query_times.append(current_time)
                self.debug_log(f"quota check success, query times: {current_query_times} > {query_per_hour}")
                return query_per_hour - current_query_times
            else:
                # 否则拒绝查询
                self.debug_log(f"quota check failed, query times: {current_query_times} >= {query_per_hour}")
                return 0