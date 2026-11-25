from enum import StrEnum


class Role(StrEnum):
    viewer = 'viewer'
    analyst = 'analyst'
    reviewer = 'reviewer'
