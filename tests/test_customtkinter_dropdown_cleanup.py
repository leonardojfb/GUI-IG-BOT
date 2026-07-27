import gui_premium_v7 as gui


def test_dropdown_destroy_unregisters_scaling_before_original_destroy():
    calls = []

    class FakeScalingBase:
        @staticmethod
        def destroy(instance):
            calls.append(("scaling", instance))

    class FakeDropdown:
        def destroy(self):
            calls.append(("dropdown-original", self))

    class FakeCombo:
        def __init__(self, dropdown):
            self._dropdown_menu = dropdown

        def destroy(self):
            calls.append(("combo-original", self))

    class FakeOption:
        def __init__(self, dropdown):
            self._dropdown_menu = dropdown

        def destroy(self):
            calls.append(("option-original", self))

    gui._install_customtkinter_dropdown_destroy_safety(
        dropdown_menu_cls=FakeDropdown,
        scaling_base_cls=FakeScalingBase,
        combo_box_cls=FakeCombo,
        option_menu_cls=FakeOption,
        tcl_error_cls=RuntimeError,
    )

    dropdown = FakeDropdown()
    dropdown.destroy()

    assert calls == [("scaling", dropdown), ("dropdown-original", dropdown)]


def test_combo_and_option_destroy_cleanup_their_dropdown_menu_first():
    calls = []

    class FakeScalingBase:
        @staticmethod
        def destroy(instance):
            calls.append(("scaling", instance))

    class FakeDropdown:
        def destroy(self):
            calls.append(("dropdown-original", self))

    class FakeCombo:
        def __init__(self, dropdown):
            self._dropdown_menu = dropdown

        def destroy(self):
            calls.append(("combo-original", self))

    class FakeOption:
        def __init__(self, dropdown):
            self._dropdown_menu = dropdown

        def destroy(self):
            calls.append(("option-original", self))

    gui._install_customtkinter_dropdown_destroy_safety(
        dropdown_menu_cls=FakeDropdown,
        scaling_base_cls=FakeScalingBase,
        combo_box_cls=FakeCombo,
        option_menu_cls=FakeOption,
        tcl_error_cls=RuntimeError,
    )

    combo_dropdown = FakeDropdown()
    combo = FakeCombo(combo_dropdown)
    combo.destroy()

    option_dropdown = FakeDropdown()
    option = FakeOption(option_dropdown)
    option.destroy()

    assert calls == [
        ("scaling", combo_dropdown),
        ("dropdown-original", combo_dropdown),
        ("combo-original", combo),
        ("scaling", option_dropdown),
        ("dropdown-original", option_dropdown),
        ("option-original", option),
    ]
