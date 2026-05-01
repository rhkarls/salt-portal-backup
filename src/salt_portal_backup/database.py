# SPDX-FileCopyrightText: 2024-present Reinert Huseby Karlsen <rhkarls@proton.me>
#
# SPDX-License-Identifier: BSD-3-Clause

from datetime import datetime
from pathlib import Path

import sqlalchemy
from sqlalchemy import CheckConstraint, ForeignKey, create_engine
from sqlalchemy.dialects.sqlite import (
    TEXT,
)  # not strictly necessary since sqlite use type affinity, but makes the type explicit
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DATABASE_VERSION = 2


class Base(DeclarativeBase): ...


class Station(Base):
    __tablename__ = "station"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_name: Mapped[str] = mapped_column(TEXT)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="stations")
    cft_1: Mapped[float] = mapped_column()
    cft_2: Mapped[float] = mapped_column()
    cft_3: Mapped[float] = mapped_column()
    measurements: Mapped["Measurement"] = relationship(back_populates="station")
    measurements_raw: Mapped["MeasurementRaw"] = relationship(back_populates="station")
    calibrations: Mapped["Calibration"] = relationship(back_populates="station")
    calibrations_raw: Mapped["CalibrationRaw"] = relationship(back_populates="station")
    rating_curves: Mapped["RatingCurve"] = relationship(back_populates="station")


class Project(Base):
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_name: Mapped[str] = mapped_column(TEXT)
    stations: Mapped["Station"] = relationship(back_populates="project")


class Measurement(Base):
    __tablename__ = "measurement"
    measurement_id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("station.id"))
    station: Mapped["Station"] = relationship(back_populates="measurements")
    group_id: Mapped[int] = mapped_column(ForeignKey("measurement_group.id"), nullable=True)
    group: Mapped["MeasurementGroup"] = relationship(back_populates="measurements")
    datetime_start: Mapped[str] = mapped_column(TEXT)
    datetime_end: Mapped[str] = mapped_column(TEXT)
    upstream_probe: Mapped[bool] = mapped_column()
    flow_cms: Mapped[float] = mapped_column()
    uncertainty_percent: Mapped[float] = mapped_column()
    notes: Mapped[str] = mapped_column(TEXT, nullable=True)
    datetime_modified: Mapped[str] = mapped_column(TEXT, nullable=True)
    modified_by: Mapped[str] = mapped_column(TEXT, nullable=True)
    locked_update_delete: Mapped[int] = mapped_column(nullable=True)
    locked_by: Mapped[str] = mapped_column(TEXT, nullable=True)
    party: Mapped[str] = mapped_column(TEXT, nullable=True)
    created_by: Mapped[str] = mapped_column(TEXT, nullable=True)
    stage_m: Mapped[float] = mapped_column(nullable=True)
    stage_datetime: Mapped[str] = mapped_column(TEXT, nullable=True)
    dl_stage_m: Mapped[float] = mapped_column(nullable=True)
    ref_stage_m: Mapped[float] = mapped_column(nullable=True)
    type: Mapped[str] = mapped_column(TEXT, nullable=True)
    filename: Mapped[str] = mapped_column(TEXT)
    channel_name: Mapped[str] = mapped_column(TEXT, nullable=True)
    rating_curve_ids: Mapped[str] = mapped_column(TEXT, nullable=True)
    probe_serial_number: Mapped[str] = mapped_column(TEXT, nullable=True)
    sd_file_id: Mapped[int] = mapped_column(nullable=True)
    sdiq_mass_nacl_kg: Mapped[float] = mapped_column(nullable=True)
    sdiq_cft: Mapped[float] = mapped_column(nullable=True)
    #states: Mapped[str] = mapped_column(TEXT, nullable=True)
    csv_data: Mapped["MeasurementCSVData"] = relationship(back_populates="measurement")


class MeasurementCSVData(Base):
    __tablename__ = "measurement_csv_data"
    measurement_id: Mapped[int] = mapped_column(
        ForeignKey("measurement.measurement_id"), primary_key=True
    )  # Should be 1-to-1, TODO OK? better to use separate id to make sure?
    measurement: Mapped["Measurement"] = relationship(back_populates="csv_data")
    csv_data: Mapped[str] = mapped_column(TEXT)


class MeasurementGroup(Base):
    __tablename__ = "measurement_group"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_summary: Mapped[str] = mapped_column(TEXT)
    measurements: Mapped["Measurement"] = relationship(back_populates="group")


class Calibration(Base):
    __tablename__ = "calibration"
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("station.id"))
    station: Mapped["Station"] = relationship(back_populates="calibrations")
    datetime_of_calibration: Mapped[str] = mapped_column(TEXT)
    coeff_var_regression_r2: Mapped[float] = mapped_column()
    cf_t: Mapped[float] = mapped_column()
    cf_t_uncertainty: Mapped[float] = mapped_column()
    volume_distilled_water_calibration_l: Mapped[float] = mapped_column()
    mass_salt_calibration_mg: Mapped[float] = mapped_column()
    volume_stream_water_calibration_l: Mapped[float] = mapped_column()
    volume_injection_calibration_solution_ml: Mapped[float] = mapped_column()
    ec_t_step_1: Mapped[float] = mapped_column()
    ec_t_step_2: Mapped[float] = mapped_column()
    ec_t_step_3: Mapped[float] = mapped_column()
    ec_t_step_4: Mapped[float] = mapped_column()
    ec_t_step_5: Mapped[float] = mapped_column()
    filename: Mapped[str] = mapped_column(TEXT)


class Version(Base):
    __tablename__ = "version"
    id: Mapped[int] = mapped_column(CheckConstraint("id = 0"), primary_key=True)
    database_version: Mapped[int] = mapped_column()
    salt_portal_version: Mapped[str] = mapped_column(TEXT)
    salt_portal_backup_version: Mapped[str] = mapped_column(TEXT)
    datetime_created: Mapped[str] = mapped_column(TEXT)
    created_by_user: Mapped[str] = mapped_column(TEXT)


class RatingCurve(Base):
    __tablename__ = "ratingcurve"
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("station.id"))
    station: Mapped["Station"] = relationship(back_populates="rating_curves")


class StationListRaw(Base):
    __tablename__ = "station_list_raw"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_station_data: Mapped[str] = mapped_column(TEXT)


class MeasurementRaw(Base):
    __tablename__ = "measurement_raw"
    station_id: Mapped[int] = mapped_column(ForeignKey("station.id"), primary_key=True)
    station: Mapped["Station"] = relationship(back_populates="measurements_raw")
    station_raw_measurement_data: Mapped[str] = mapped_column(TEXT)


class CalibrationRaw(Base):
    __tablename__ = "calibration_raw"
    station_id: Mapped[int] = mapped_column(ForeignKey("station.id"), primary_key=True)
    station: Mapped["Station"] = relationship(back_populates="calibrations_raw")
    station_raw_calibration_data: Mapped[str] = mapped_column(TEXT)


def initialize_database(database_name: str = None) -> sqlalchemy.Engine:
    """Initialize the SQLite database for the backup.

    If a database name is provided, it will be used, otherwise a new database will be
    created in the users home folder with a name based on the current date and time.

    If a database with the provided name already exists, a warning is printed and the
    existing database is used (TODO implement).
    """

    if database_name is None:
        db_filename = "salt_portal_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
        database_name = str(
            Path.home() / db_filename
        )  # FIXME can we do create_engine without str concat?

    elif Path(database_name).exists():
        raise NotImplementedError("Database file already exists. Backup to existing database is not implemented yet.")
        print(
            "Database file already exists. It is recommended to backup to a new database. "
            "Proceed with existing database, possibly leading to data loss of already existing data?"
        )
        # TODO implement

    db_engine = create_engine("sqlite:///" + database_name, echo=False)

    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)

    print("Backup to " + database_name)

    return db_engine
