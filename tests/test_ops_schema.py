import pytest

from server.ops_schema import serialize_ops, validate_ops


class TestValidMinimalOps:
    def test_create_frame(self):
        batch = validate_ops([{"op": "CREATE_FRAME", "tempId": "f1"}])
        assert len(batch.ops) == 1
        assert batch.ops[0].op == "CREATE_FRAME"

    def test_create_rectangle(self):
        batch = validate_ops([{"op": "CREATE_RECTANGLE", "tempId": "r1"}])
        assert batch.ops[0].op == "CREATE_RECTANGLE"

    def test_create_ellipse(self):
        batch = validate_ops([{"op": "CREATE_ELLIPSE", "tempId": "e1"}])
        assert batch.ops[0].op == "CREATE_ELLIPSE"

    def test_create_text(self):
        batch = validate_ops([{"op": "CREATE_TEXT", "tempId": "t1", "text": "hello"}])
        assert batch.ops[0].op == "CREATE_TEXT"
        assert batch.ops[0].text == "hello"

    def test_update_node(self):
        batch = validate_ops([{"op": "UPDATE_NODE", "tempId": "u1", "nodeId": "123:456"}])
        assert batch.ops[0].op == "UPDATE_NODE"

    def test_delete_node(self):
        batch = validate_ops([{"op": "DELETE_NODE", "tempId": "d1", "nodeId": "123:456"}])
        assert batch.ops[0].op == "DELETE_NODE"


class TestParentReferences:
    def test_parent_temp_id_back_reference(self):
        batch = validate_ops([
            {"op": "CREATE_FRAME", "tempId": "f1"},
            {"op": "CREATE_RECTANGLE", "tempId": "r1", "parentTempId": "f1"},
        ])
        assert batch.ops[1].parent_temp_id == "f1"

    def test_parent_node_id(self):
        batch = validate_ops([
            {"op": "CREATE_RECTANGLE", "tempId": "r1", "parentNodeId": "123:456"},
        ])
        assert batch.ops[0].parent_node_id == "123:456"


class TestSerialization:
    def test_serialize_produces_camel_case(self):
        batch = validate_ops([
            {"op": "CREATE_FRAME", "tempId": "f1", "cornerRadius": 8},
        ])
        result = serialize_ops(batch)
        assert result[0]["tempId"] == "f1"
        assert result[0]["cornerRadius"] == 8
        assert "corner_radius" not in result[0]

    def test_serialize_excludes_none(self):
        batch = validate_ops([{"op": "CREATE_FRAME", "tempId": "f1"}])
        result = serialize_ops(batch)
        assert "parentTempId" not in result[0]
        assert "fills" not in result[0]


class TestFontWeight:
    def test_numeric_400_to_regular(self):
        batch = validate_ops([
            {"op": "CREATE_TEXT", "tempId": "t1", "text": "hi", "fontWeight": 400},
        ])
        assert batch.ops[0].font_weight == "Regular"

    def test_numeric_700_to_bold(self):
        batch = validate_ops([
            {"op": "CREATE_TEXT", "tempId": "t1", "text": "hi", "fontWeight": 700},
        ])
        assert batch.ops[0].font_weight == "Bold"

    def test_string_passthrough(self):
        batch = validate_ops([
            {"op": "CREATE_TEXT", "tempId": "t1", "text": "hi", "fontWeight": "Medium"},
        ])
        assert batch.ops[0].font_weight == "Medium"

    def test_invalid_numeric_rejects(self):
        with pytest.raises(ValueError, match="Invalid numeric fontWeight"):
            validate_ops([
                {"op": "CREATE_TEXT", "tempId": "t1", "text": "hi", "fontWeight": 999},
            ])

    def test_invalid_string_rejects(self):
        with pytest.raises(ValueError, match="Invalid fontWeight"):
            validate_ops([
                {"op": "CREATE_TEXT", "tempId": "t1", "text": "hi", "fontWeight": "SuperHeavy"},
            ])


class TestStrokeAlign:
    def test_normalize_lowercase(self):
        batch = validate_ops([
            {"op": "CREATE_RECTANGLE", "tempId": "r1", "stroke": {"r": 1, "g": 0, "b": 0, "align": "inside"}},
        ])
        assert batch.ops[0].stroke.align == "INSIDE"


class TestInvalidOps:
    def test_color_out_of_range_high(self):
        with pytest.raises(ValueError):
            validate_ops([
                {"op": "CREATE_RECTANGLE", "tempId": "r1", "fills": [{"r": 1.5, "g": 0, "b": 0}]},
            ])

    def test_color_out_of_range_negative(self):
        with pytest.raises(ValueError):
            validate_ops([
                {"op": "CREATE_RECTANGLE", "tempId": "r1", "fills": [{"r": 0, "g": -0.1, "b": 0}]},
            ])

    def test_missing_temp_id(self):
        with pytest.raises(ValueError):
            validate_ops([{"op": "CREATE_FRAME"}])

    def test_unknown_op_type(self):
        with pytest.raises(ValueError, match="invalid op type"):
            validate_ops([{"op": "UNKNOWN_OP", "tempId": "x1"}])

    def test_duplicate_temp_id(self):
        with pytest.raises(ValueError, match="Duplicate tempId"):
            validate_ops([
                {"op": "CREATE_FRAME", "tempId": "f1"},
                {"op": "CREATE_RECTANGLE", "tempId": "f1"},
            ])

    def test_forward_reference(self):
        with pytest.raises(ValueError, match="not found in preceding ops"):
            validate_ops([
                {"op": "CREATE_RECTANGLE", "tempId": "r1", "parentTempId": "f1"},
                {"op": "CREATE_FRAME", "tempId": "f1"},
            ])

    def test_both_parent_ids(self):
        with pytest.raises(ValueError, match="either parentTempId or parentNodeId"):
            validate_ops([
                {"op": "CREATE_FRAME", "tempId": "f1"},
                {"op": "CREATE_RECTANGLE", "tempId": "r1", "parentTempId": "f1", "parentNodeId": "123:456"},
            ])

    def test_batch_over_100(self):
        ops = [{"op": "CREATE_FRAME", "tempId": f"f{i}"} for i in range(101)]
        with pytest.raises(ValueError, match="Too many ops"):
            validate_ops(ops)


class TestDimensionBoundaries:
    def test_width_zero_fails(self):
        with pytest.raises(ValueError):
            validate_ops([{"op": "CREATE_RECTANGLE", "tempId": "r1", "w": 0}])

    def test_width_over_max_fails(self):
        with pytest.raises(ValueError):
            validate_ops([{"op": "CREATE_RECTANGLE", "tempId": "r1", "w": 10001}])

    def test_width_at_max_passes(self):
        batch = validate_ops([{"op": "CREATE_RECTANGLE", "tempId": "r1", "w": 10000}])
        assert batch.ops[0].w == 10000


class TestUpdateNodeFontWeight:
    def test_numeric_normalization(self):
        batch = validate_ops([
            {"op": "UPDATE_NODE", "tempId": "u1", "nodeId": "1:2", "fontWeight": 400},
        ])
        assert batch.ops[0].font_weight == "Regular"

    def test_none_passthrough(self):
        batch = validate_ops([
            {"op": "UPDATE_NODE", "tempId": "u1", "nodeId": "1:2"},
        ])
        assert batch.ops[0].font_weight is None
