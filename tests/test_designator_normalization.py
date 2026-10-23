"""Tests for designator normalization in BOM/PnP files."""

import pytest
from smt_processor import normalize_designators


class TestNormalizeDesignators:
    """Test suite for designator normalization function."""

    def test_normal_designators(self):
        """Test normal comma-separated designators."""
        result, warnings = normalize_designators("C1,C2,C3,C4")
        assert result == ["C1", "C2", "C3", "C4"]
        assert warnings == []

    def test_sticky_designators_single_pair(self):
        """Test sticky designators without comma (e.g., C29C30)."""
        result, warnings = normalize_designators("C25,C27,C29C30,C32")
        assert result == ["C25", "C27", "C29", "C30", "C32"]
        assert len(warnings) == 1
        assert "C29C30" in warnings[0]
        assert "C29" in warnings[0] and "C30" in warnings[0]

    def test_sticky_designators_multiple_pairs(self):
        """Test multiple sticky designators in one string."""
        result, warnings = normalize_designators("C29C30,C69C70")
        assert result == ["C29", "C30", "C69", "C70"]
        assert len(warnings) == 2

    def test_spaces_instead_of_commas(self):
        """Test spaces used instead of commas."""
        result, warnings = normalize_designators("C72 C83")
        assert result == ["C72", "C83"]
        assert len(warnings) == 1
        assert "C72 C83" in warnings[0]

    def test_mixed_separators(self):
        """Test mix of commas and spaces."""
        result, warnings = normalize_designators("C1,C2 C3,C4 C5")
        assert result == ["C1", "C2", "C3", "C4", "C5"]
        assert len(warnings) >= 1

    def test_sticky_with_spaces(self):
        """Test sticky designators with spaces around."""
        result, warnings = normalize_designators("C25, C29C30 , C32")
        assert result == ["C25", "C29", "C30", "C32"]
        assert len(warnings) == 1

    def test_resistor_sticky_designators(self):
        """Test sticky resistor designators."""
        result, warnings = normalize_designators("R258,R259R261,R262")
        assert result == ["R258", "R259", "R261", "R262"]
        assert len(warnings) == 1
        assert "R259R261" in warnings[0]

    def test_mixed_prefix_sticky(self):
        """Test sticky designators with different prefixes."""
        result, warnings = normalize_designators("C10R20")
        assert result == ["C10", "R20"]
        assert len(warnings) == 1

    def test_multiple_numbers_sticky(self):
        """Test sticky designators with multiple number groups."""
        result, warnings = normalize_designators("C100C200C300")
        assert result == ["C100", "C200", "C300"]
        assert len(warnings) == 1

    def test_empty_string(self):
        """Test empty string input."""
        result, warnings = normalize_designators("")
        assert result == []
        assert warnings == []

    def test_single_designator(self):
        """Test single designator."""
        result, warnings = normalize_designators("C1")
        assert result == ["C1"]
        assert warnings == []

    def test_designators_with_leading_trailing_spaces(self):
        """Test designators with extra spaces."""
        result, warnings = normalize_designators("  C1 , C2 , C3  ")
        assert result == ["C1", "C2", "C3"]
        assert warnings == []

    def test_case_insensitive(self):
        """Test that function handles different cases."""
        result, warnings = normalize_designators("c1,C2,c3C4")
        # Function should preserve case or normalize to upper
        assert len(result) == 4
        assert "C4" in result or "c4" in result

    def test_complex_prefix(self):
        """Test designators with complex prefixes."""
        result, warnings = normalize_designators("LED1LED2")
        assert result == ["LED1", "LED2"]
        assert len(warnings) == 1

    def test_unusual_designator_kept(self):
        """Test that unusual designators are kept (no format validation)."""
        result, warnings = normalize_designators("C1,INVALID,C2")
        assert result == ["C1", "INVALID", "C2"]
        assert warnings == []  # No warnings for unusual formats

    def test_real_world_example_1(self):
        """Test real-world example from BOM file."""
        result, warnings = normalize_designators("C6,C7,C8,C9,C10,C11,C12,C13,C14,C15,C18,C19,C21,C22,C25,C27,C29C30,C32,C34,C38,C45,C46,C47,C54,C116,C117,C61,C64,C65,C69,C72 C83,C84,C104,C123")
        assert "C29" in result
        assert "C30" in result
        assert "C72" in result
        assert "C83" in result
        assert len(warnings) == 2  # C29C30 and C72 C83

    def test_real_world_example_2(self):
        """Test another real-world example."""
        result, warnings = normalize_designators("R258,R259R261,R262")
        assert result == ["R258", "R259", "R261", "R262"]
        assert len(warnings) == 1

    def test_preserves_order(self):
        """Test that order of designators is preserved."""
        result, warnings = normalize_designators("C3,C1,C2")
        assert result == ["C3", "C1", "C2"]

    def test_duplicate_designators(self):
        """Test handling of duplicate designators."""
        result, warnings = normalize_designators("C1,C1,C2")
        # Function should keep duplicates (user can decide later)
        assert result == ["C1", "C1", "C2"]
