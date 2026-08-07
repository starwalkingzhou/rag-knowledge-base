import json
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import NotFoundError, ValidationError

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"


@dataclass(frozen=True)
class EvaluationCase:
    """单条评测样本。

    expected_keywords 与 expected_document_names 配合做"引用命中率"判定:
    - 命中文档名 -> 视为引用命中
    - 命中任一关键词 (在 actual citations 的 quote 拼接里) -> 视为引用命中
    """

    case_id: str
    question: str
    expected_answer: str
    expected_document_names: list[str]
    expected_keywords: list[str]
    should_refuse: bool
    tags: list[str]


def list_datasets() -> list[tuple[str, int]]:
    """枚举 datasets/ 下所有 jsonl，返回 (name, size) 二元组列表。"""
    if not DATASETS_DIR.exists():
        return []
    result: list[tuple[str, int]] = []
    for path in sorted(DATASETS_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        result.append((path.stem, count))
    return result


def load_dataset(name: str) -> list[EvaluationCase]:
    path = DATASETS_DIR / f"{name}.jsonl"
    if not path.exists():
        raise NotFoundError(f"评测集不存在：{name}")

    cases: list[EvaluationCase] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"评测集 {name} 第 {line_no} 行 JSON 非法：{exc.msg}"
                ) from exc
            cases.append(_parse_case(data, line_no=line_no, dataset=name))
    return cases


def _ensure_list(
    value,
    *,
    field_name: str,
    line_no: int,
    dataset: str,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(
            f"评测集 {dataset} 第 {line_no} 行字段「{field_name}」类型错误："
            f"应为数组，实际为 {type(value).__name__}"
        )
    return [str(x) for x in value]


def _parse_case(data: dict, *, line_no: int, dataset: str) -> EvaluationCase:
    try:
        # id 必须是标量（str / int）
        raw_id = data["id"]
        if not isinstance(raw_id, (str, int)):
            raise ValidationError(
                f"评测集 {dataset} 第 {line_no} 行字段「id」类型错误：应为字符串或数字"
            )

        # question 不允许空字符串
        question = str(data["question"]).strip()
        if not question:
            raise ValidationError(
                f"评测集 {dataset} 第 {line_no} 行字段「question」不能为空"
            )

        # should_refuse 严格布尔，避免 bool("false") 变 True
        raw_refuse = data.get("should_refuse", False)
        if not isinstance(raw_refuse, bool):
            raise ValidationError(
                f"评测集 {dataset} 第 {line_no} 行字段「should_refuse」类型错误："
                f"应为布尔值 true/false，实际为 {type(raw_refuse).__name__} = {raw_refuse!r}"
            )

        return EvaluationCase(
            case_id=str(raw_id),
            question=question,
            expected_answer=str(data.get("expected_answer", "")),
            expected_document_names=_ensure_list(
                data.get("expected_document_names"),
                field_name="expected_document_names",
                line_no=line_no,
                dataset=dataset,
            ),
            expected_keywords=_ensure_list(
                data.get("expected_keywords"),
                field_name="expected_keywords",
                line_no=line_no,
                dataset=dataset,
            ),
            should_refuse=raw_refuse,
            tags=_ensure_list(
                data.get("tags"),
                field_name="tags",
                line_no=line_no,
                dataset=dataset,
            ),
        )
    except KeyError as exc:
        raise ValidationError(
            f"评测集 {dataset} 第 {line_no} 行缺失字段：{exc.args[0]}"
        ) from exc