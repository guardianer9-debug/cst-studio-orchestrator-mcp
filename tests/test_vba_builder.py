"""Tests for VBA builder module."""

from __future__ import annotations

import pytest

from mcp_cst_studio.vba_builder import VBABuilder, VBAScript, solid_ref
from mcp_cst_studio.validators import ValidationError


class TestVBABuilder:
    def test_simple_brick(self):
        vba = (
            VBABuilder("Brick")
            .call("Reset")
            .set("Name", "box1")
            .set("Component", "Antenna")
            .set("Material", "PEC")
            .set_double("Xrange", -10, 10)
            .set_double("Yrange", -10, 10)
            .set_double("Zrange", 0, 5)
            .call("Create")
        )
        script = vba.build()
        assert "With Brick" in script
        assert '.Name "box1"' in script
        assert '.Component "Antenna"' in script
        assert '.Material "PEC"' in script
        assert '.Xrange "-10", "10"' in script
        assert '.Zrange "0", "5"' in script
        assert ".Create" in script
        assert "End With" in script

    def test_set_number(self):
        vba = VBABuilder("Solver").set_number("Accuracy", -40).build()
        assert '.Accuracy "-40"' in vba

    def test_set_bool(self):
        vba = VBABuilder("Mesh").set_bool("AutomaticMeshGeneration", True).build()
        assert '.AutomaticMeshGeneration "True"' in vba

    def test_set_triple(self):
        vba = VBABuilder("Transform").set_triple("Origin", 1.5, 2.5, 3.5).build()
        assert '.Origin "1.5", "2.5", "3.5"' in vba

    def test_raw_line(self):
        vba = VBABuilder("Solid").raw_line('Solid.Add "comp1:s1", "comp1:s2"').build()
        assert 'Solid.Add "comp1:s1", "comp1:s2"' in vba

    def test_raw_line_blocks_dangerous(self):
        with pytest.raises(ValidationError, match="Shell"):
            VBABuilder("Obj").raw_line("Shell cmd.exe")

    def test_escape_quotes(self):
        vba = VBABuilder("Brick").set("Name", 'my "special" brick').build()
        assert '.Name "my ""special"" brick"' in vba

    def test_reset_clears(self):
        builder = VBABuilder("Brick")
        builder.set("Name", "old")
        builder.reset()
        builder.set("Name", "new")
        script = builder.build()
        assert "old" not in script
        assert "new" in script

    def test_float_formatting(self):
        vba = VBABuilder("Brick").set_double("Xrange", 0.001, 1e6).build()
        assert '"0.001"' in vba
        assert '"1000000"' in vba

    def test_integer_formatting(self):
        vba = VBABuilder("Brick").set_number("Count", 5.0).build()
        assert '"5"' in vba


class TestVBAScript:
    def test_multi_block(self):
        b1 = VBABuilder("Material").call("Reset").set("Name", "mat1").call("Create")
        b2 = VBABuilder("Brick").call("Reset").set("Name", "box1").call("Create")

        script = VBAScript().add_block(b1).add_block(b2).build()
        assert "With Material" in script
        assert "With Brick" in script
        assert script.index("Material") < script.index("Brick")

    def test_with_comment(self):
        script = VBAScript().add_comment("Create antenna").add_raw('Dim x As Double').build()
        assert "' Create antenna" in script
        assert "Dim x As Double" in script

    def test_raw_blocks_dangerous(self):
        with pytest.raises(ValidationError):
            VBAScript().add_raw("CreateObject(\"WScript.Shell\")")


class TestSolidRef:
    def test_valid(self):
        assert solid_ref("Antenna", "Patch") == "Antenna:Patch"

    def test_empty_component(self):
        with pytest.raises(ValidationError):
            solid_ref("", "Patch")

    def test_empty_solid(self):
        with pytest.raises(ValidationError):
            solid_ref("Antenna", "")
