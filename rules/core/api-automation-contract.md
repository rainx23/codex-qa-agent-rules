# API Automation Fixed Health Contract

API 自动化仅支持 `assertion_scope=parameter_health`。唯一健康检查按固定顺序恰好为 `content.code equals 0` 和 `content.msg equals "OK"`，不允许额外检查或自定义成功协议。

Model、Artifact 和 Python 脚本必须使用同一固定契约。`content.code` 的 expected 必须是非布尔整数 `0`；`content.msg` 必须精确为字符串 `OK`。`business_assertions` 必须存在且为空数组。

正式 Artifact 必须引用真实 Model 路径、ID 和 SHA-256，且 method、URL/path、参数、环境变量和健康检查完全一致。脚本必须从真实 `response` 对象执行两条精确断言，禁止注释伪装、固定局部变量、默认成功值、吞掉断言异常及额外业务断言。

正式 CLI 必须传入 Artifact 和 Model；CI 不得使用 draft、legacy 或忽略退出码。接口不符合固定响应协议时只能进入 pending 或标记不适用。
