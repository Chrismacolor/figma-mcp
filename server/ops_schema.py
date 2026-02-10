from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# Numeric font weight → Figma string name mapping
FONT_WEIGHT_MAP: dict[int, str] = {
    100: "Thin",
    200: "Extra Light",
    300: "Light",
    400: "Regular",
    500: "Medium",
    600: "Semi Bold",
    700: "Bold",
    800: "Extra Bold",
    900: "Black",
}

VALID_FONT_WEIGHTS = set(FONT_WEIGHT_MAP.values())


class Fill(BaseModel):
    r: float = Field(ge=0, le=1)
    g: float = Field(ge=0, le=1)
    b: float = Field(ge=0, le=1)
    a: float = Field(default=1, ge=0, le=1)


class BaseOp(BaseModel):
    temp_id: str = Field(alias="tempId")
    parent_temp_id: str | None = Field(default=None, alias="parentTempId")
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    name: str | None = None
    x: float = Field(default=0, ge=-10000, le=10000)
    y: float = Field(default=0, ge=-10000, le=10000)
    fills: list[Fill] | None = None

    model_config = {"populate_by_name": True}


class CreateFrameOp(BaseOp):
    op: Literal["CREATE_FRAME"]
    w: float = Field(default=100, gt=0, le=10000, alias="w")
    h: float = Field(default=100, gt=0, le=10000, alias="h")
    corner_radius: float = Field(default=0, ge=0, le=1000, alias="cornerRadius")
    layout_mode: Literal["NONE", "HORIZONTAL", "VERTICAL"] = Field(
        default="NONE", alias="layoutMode"
    )
    item_spacing: float = Field(default=0, ge=0, le=10000, alias="itemSpacing")
    padding_left: float = Field(default=0, ge=0, le=10000, alias="paddingLeft")
    padding_right: float = Field(default=0, ge=0, le=10000, alias="paddingRight")
    padding_top: float = Field(default=0, ge=0, le=10000, alias="paddingTop")
    padding_bottom: float = Field(default=0, ge=0, le=10000, alias="paddingBottom")
    primary_axis_align: Literal["MIN", "CENTER", "MAX", "SPACE_BETWEEN"] = Field(
        default="MIN", alias="primaryAxisAlignItems"
    )
    counter_axis_align: Literal["MIN", "CENTER", "MAX"] = Field(
        default="MIN", alias="counterAxisAlignItems"
    )
    clips_content: bool = Field(default=False, alias="clipsContent")


class CreateRectangleOp(BaseOp):
    op: Literal["CREATE_RECTANGLE"]
    w: float = Field(default=100, gt=0, le=10000, alias="w")
    h: float = Field(default=100, gt=0, le=10000, alias="h")
    corner_radius: float = Field(default=0, ge=0, le=1000, alias="cornerRadius")
    opacity: float = Field(default=1, ge=0, le=1)


class CreateEllipseOp(BaseOp):
    op: Literal["CREATE_ELLIPSE"]
    w: float = Field(default=100, gt=0, le=10000, alias="w")
    h: float = Field(default=100, gt=0, le=10000, alias="h")
    opacity: float = Field(default=1, ge=0, le=1)


class CreateTextOp(BaseOp):
    op: Literal["CREATE_TEXT"]
    text: str
    font_size: float = Field(default=16, ge=1, le=1000, alias="fontSize")
    font_family: str = Field(default="Inter", alias="fontFamily")
    font_weight: str = Field(default="Regular", alias="fontWeight")
    text_align_horizontal: Literal["LEFT", "CENTER", "RIGHT", "JUSTIFIED"] = Field(
        default="LEFT", alias="textAlignHorizontal"
    )
    text_auto_resize: Literal["NONE", "WIDTH_AND_HEIGHT", "HEIGHT", "TRUNCATE"] = Field(
        default="WIDTH_AND_HEIGHT", alias="textAutoResize"
    )
    w: float | None = Field(default=None, gt=0, le=10000, alias="w")
    h: float | None = Field(default=None, gt=0, le=10000, alias="h")
    line_height: float | None = Field(default=None, ge=1, le=10000, alias="lineHeight")
    letter_spacing: float | None = Field(default=None, ge=-100, le=100, alias="letterSpacing")
    opacity: float = Field(default=1, ge=0, le=1)

    @field_validator("font_weight", mode="before")
    @classmethod
    def normalize_font_weight(cls, v: str | int) -> str:
        if isinstance(v, (int, float)):
            n = int(v)
            if n in FONT_WEIGHT_MAP:
                return FONT_WEIGHT_MAP[n]
            raise ValueError(
                f"Invalid numeric fontWeight {n}. "
                f"Use one of: {', '.join(f'{k} ({v})' for k, v in sorted(FONT_WEIGHT_MAP.items()))}"
            )
        if v not in VALID_FONT_WEIGHTS:
            raise ValueError(
                f"Invalid fontWeight '{v}'. "
                f"Use one of: {', '.join(sorted(VALID_FONT_WEIGHTS))} "
                f"or numeric: {', '.join(str(k) for k in sorted(FONT_WEIGHT_MAP))}"
            )
        return v


Op = CreateFrameOp | CreateRectangleOp | CreateEllipseOp | CreateTextOp


class OpsBatch(BaseModel):
    ops: list[Op]

    @model_validator(mode="after")
    def validate_ops(self) -> "OpsBatch":
        if len(self.ops) > 100:
            raise ValueError(f"Too many ops: {len(self.ops)} (max 100)")

        seen_ids: set[str] = set()
        for i, op in enumerate(self.ops):
            tid = op.temp_id
            if tid in seen_ids:
                raise ValueError(f"Duplicate tempId '{tid}' at op index {i}")
            seen_ids.add(tid)

            if op.parent_temp_id and op.parent_node_id:
                raise ValueError(
                    f"Op index {i}: specify either parentTempId or parentNodeId, not both"
                )

            ptid = op.parent_temp_id
            if ptid is not None and ptid not in seen_ids:
                raise ValueError(
                    f"Op index {i}: parentTempId '{ptid}' not found in preceding ops"
                )

        return self


def validate_ops(raw_ops: list[dict]) -> OpsBatch:
    """Validate raw op dicts. Raises ValueError/ValidationError on failure."""
    return OpsBatch(ops=raw_ops)


def serialize_ops(batch: OpsBatch) -> list[dict]:
    """Serialize validated ops back to dicts using camelCase aliases."""
    return [op.model_dump(by_alias=True, exclude_none=True) for op in batch.ops]
