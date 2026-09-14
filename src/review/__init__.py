"""Review helpers; heavyweight image tooling is loaded only when requested."""

__all__ = ["generate_storyboard_contact_sheet"]


def __getattr__(name):
    if name == "generate_storyboard_contact_sheet":
        from .contact_sheet import generate_storyboard_contact_sheet

        return generate_storyboard_contact_sheet
    raise AttributeError(name)
