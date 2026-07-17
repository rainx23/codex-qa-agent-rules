# Tests

规则、脚本、Schema 和 CI 契约的离线自动化测试。

## 目录定位

覆盖行为回归、生成契约、Fixture 和 Golden 输出，不依赖网络或外部服务。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `test_*.py` | 单元与集成测试 | 是 |
| `test_anti_hallucination_contracts.py` | 反幻觉、门禁、模型和 SQL 配置反例 | 是 |
| `test_anti_hallucination_fixtures.py` | 八类独立反幻觉 Fixture 的统一回归入口 | 是 |
| `fixtures/anti_hallucination/` | confirmed inference、blocking gate、DDL partial、模糊断言、缺失证据、虚构标识符、疑似缺陷、API health scope 的合法/非法输入与 Golden | 是 |
| `fixtures/` | 输入样例 | 是 |
| `golden/` | 预期输出 | 是 |

## 使用入口

- 独立反幻觉回归：`python -m unittest discover -s tests -p test_anti_hallucination_fixtures.py -v`。
- 全量回归：`python -m unittest discover -s tests -v`。

## 维护约束

- 改变规则、脚本、Schema、CI 或产物契约时必须补充或更新测试。
- Fixture 和 Golden 只服务测试，不作为业务历史版本说明。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
