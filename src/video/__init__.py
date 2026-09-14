"""Video engines with lazy loading so metadata workflows do not require OpenCV."""

__all__ = ["CinematicMotionEngine", "MotionConfig", "MotionType"]


def __getattr__(name):
    if name in __all__:
        from .cinematic_engine import CinematicMotionEngine, MotionConfig, MotionType

        return {
            "CinematicMotionEngine": CinematicMotionEngine,
            "MotionConfig": MotionConfig,
            "MotionType": MotionType,
        }[name]
    raise AttributeError(name)
