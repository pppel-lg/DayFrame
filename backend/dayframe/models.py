"""Versioned, portable archive schemas. No API-only fields are persisted."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


def utc_string(value):
    if value is None:
        return value
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('UTC timestamp with timezone required')
    return value


class ArchiveMetadata(StrictModel):
    format: Literal['dayframe-archive'] = 'dayframe-archive'
    format_version: Literal[1] = 1
    archive_id: str
    created_at_utc: str
    archive_start_date: date
    description: str = 'My personal Dayframe archive'
    _utc = field_validator('created_at_utc')(utc_string)


class Location(StrictModel):
    label: str = Field(default='', max_length=200)
    city: str = Field(default='', max_length=100)
    region: str = Field(default='', max_length=100)
    country: str = Field(default='', max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    precision: Literal['none', 'city', 'exact'] = 'none'
    source: Literal['manual'] = 'manual'

    @model_validator(mode='after')
    def coordinates(self):
        if self.precision != 'exact':
            self.latitude = self.longitude = None
        elif (self.latitude is None) != (self.longitude is None):
            raise ValueError('latitude and longitude must be provided together')
        return self


class Photo(StrictModel):
    photo_id: str
    relative_path: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    byte_size: int = Field(gt=0, le=50 * 1024 * 1024)
    mime_type: Literal['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
    captured_at_utc: str | None = None
    captured_timezone: str | None = Field(default=None, max_length=80)
    captured_offset_minutes: int | None = Field(default=None, ge=-840, le=840)
    imported_at_utc: str
    source: Literal['import', 'camera', 'mobile', 'desktop_camera'] = 'import'
    is_original: Literal[True] = True
    trashed_at_utc: str | None = None
    _utc = field_validator('captured_at_utc', 'imported_at_utc', 'trashed_at_utc')(utc_string)

    @field_validator('photo_id')
    @classmethod
    def uuid_id(cls, value):
        UUID(value)
        return value


class Entry(StrictModel):
    schema_version: Literal[1] = 1
    entry_id: str
    record_date: date
    status: Literal['recorded', 'skipped'] = 'skipped'
    primary_photo_id: str | None = None
    mood: str = Field(default='', max_length=80)
    note: str = Field(default='', max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    location: Location = Field(default_factory=Location)
    photos: list[Photo] = Field(default_factory=list, max_length=1000)
    created_at_utc: str
    updated_at_utc: str
    _utc = field_validator('created_at_utc', 'updated_at_utc')(utc_string)

    @field_validator('tags')
    @classmethod
    def valid_tags(cls, value):
        if any(len(tag) > 80 for tag in value):
            raise ValueError('tag exceeds 80 characters')
        return list(dict.fromkeys(tag.strip() for tag in value if tag.strip()))

    @model_validator(mode='after')
    def primary_belongs(self):
        ids = [p.photo_id for p in self.photos]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate photo ID')
        paths = [p.relative_path for p in self.photos]
        if len(paths) != len(set(paths)):
            raise ValueError('duplicate media path')
        if self.primary_photo_id is not None:
            primary = next((p for p in self.photos if p.photo_id == self.primary_photo_id), None)
            if primary is None or primary.trashed_at_utc:
                raise ValueError('primary must belong to this entry and be active')
        if self.status == 'recorded' and not self.primary_photo_id:
            raise ValueError('recorded entry requires primary photo')
        return self


class Settings(StrictModel):
    reminder_enabled: bool = False
    reminder_time: str = Field(default='09:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    mirror_preview: bool = True
    mirror_output: bool = False
    week_starts_monday: bool = True


class Letter(StrictModel):
    schema_version: Literal[1] = 1
    letter_id: str
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100000)
    unlock_date: date
    created_on_date: date
    created_at_utc: str
    _utc = field_validator('created_at_utc')(utc_string)


class EntryUpdate(StrictModel):
    mood: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=20000)
    tags: list[str] | None = Field(default=None, max_length=30)
    location: Location | None = None
    status: Literal['recorded', 'skipped'] | None = None
    primary_photo_id: str | None = None
    confirmed: bool = False


class PhotoChoice(StrictModel):
    photo_id: str
    confirmed: Literal[True]


class UntrashChoice(StrictModel):
    photo_id: str


class JobRequest(StrictModel):
    kind: Literal['verify', 'backup', 'rebuild', 'export_calendar', 'report', 'video']
    year: int | None = Field(default=None, ge=1900, le=9999)
    start: date | None = None
    end: date | None = None
    fps: float = Field(default=5, ge=.2, le=60)
    include_notes: bool = False


class RestoreRequest(StrictModel):
    name: str
    target_name: str
    confirmed: Literal[True]


class LetterRequest(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100000)
    unlock_date: date
    created_on_date: date
