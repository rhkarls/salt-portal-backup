# SPDX-FileCopyrightText: 2024-present Reinert Huseby Karlsen <rhkarls@proton.me>
#
# SPDX-License-Identifier: BSD-3-Clause

import datetime
import re
import warnings
from pathlib import Path

import numpy as np
import requests
from bs4 import BeautifulSoup as bs
from sqlalchemy.orm import Session
from tqdm import tqdm

from salt_portal_backup import __version__ as spb_version

from .database import (
    DATABASE_VERSION,
    Calibration,
    CalibrationRaw,
    Measurement,
    MeasurementCSVData,
    MeasurementGroup,
    MeasurementRaw,
    Project,
    Station,
    StationListRaw,
    # RatingCurve,
    Version,
    initialize_database,
)
from .web_scraping import (
    URL_LOGIN,
    get_projects_stations,
    get_station_data,
    header_data_template,
    login_salt_portal,
)

SUPPORTED_SP_VERSION = "1.0.2"

DESC_WIDTH = 34


def _fmt_desc(text: str, width: int = DESC_WIDTH) -> str:
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def run_backup(username: str, password: str, database_path: str | Path | None = None):

    db_engine = initialize_database(database_name=database_path)

    with requests.session() as s_request, Session(db_engine) as s_db:
        req = s_request.get(URL_LOGIN).text
        html = bs(req, "html.parser")
        token = html.find("input", {"name": "csrfmiddlewaretoken"}).attrs["value"]

        login_res = login_salt_portal(s_request, token, username, password)

        html_main_page = bs(login_res.text, "html.parser")

        # SP returns 200 even if the login fails
        # so we need to check the html for login errors or if we are still on the login page
        # we also check if html_sidenav is present, which is only present on the authenticated page currently
        # all of these checks are weak since the login page and behavior of SP can change
        login_error = html_main_page.select_one(".auth-form-errors .errorlist")
        if login_error is not None:
            error_message = login_error.get_text(" ", strip=True)
            raise Exception(f"Login failed: {error_message}")

        login_form = html_main_page.select_one('form[action="/accounts/login/"]')
        password_input = html_main_page.select_one('input[name="login-password"]')
        if login_form is not None or password_input is not None:
            raise Exception("Login failed: still on login page")

        html_sidenav = html_main_page.find("div", class_="wh-sidenav-content")
        if html_sidenav is None:
            raise Exception("Login failed: authenticated page not detected")
        full_version_tag = html_sidenav.find("p", string=re.compile("Salt Portal "))
        try:
            sp_semver = full_version_tag.text.strip().removeprefix("Salt Portal ")
        except AttributeError:
            sp_semver = (
                ""  # empty string instead of None, else it fails on db insert later
            )

        if sp_semver == "":
            warnings.warn(
                "Unable to parse Salt Portal version number.\n"
                "This may indicate authentication issues or that the Salt Portal website "
                "has changed. Please report at https://github.com/rhkarls/salt-portal-backup/issues "
                "if backup does not work.",
                stacklevel=2,
            )
        elif sp_semver != SUPPORTED_SP_VERSION:
            warnings.warn(
                f"The current version of Salt Portal Backup that you are using (package version {spb_version}), is not "
                f"tested against the Salt Portal version that is currently live on the interweb ({sp_semver}). This may cause issues "
                f"with the backup, as the data schema may change. Supported "
                f"Salt Portal version is {SUPPORTED_SP_VERSION}."
                f"\n\nPlease check for updates of the Salt Portal Backup package, "
                f"and if no updates are available please submit an issue at https://github.com/rhkarls/salt-portal-backup/issues "
                f"and include the versions printed in this message.",
                stacklevel=2,
            )

        db_version = Version(
            id=0,
            database_version=DATABASE_VERSION,
            salt_portal_version=sp_semver,
            datetime_created=datetime.datetime.now(datetime.UTC).isoformat(
                timespec="seconds"
            ),
            created_by_user=username,
            salt_portal_backup_version=spb_version,
        )

        s_db.add(db_version)
        s_db.commit()

        # set the token for all the headers in this session
        header_data_template["Cookie"] = header_data_template["Cookie"].format(
            token=token
        )

        header_get_organization = header_data_template.copy()
        projects, stations, stations_csv = get_projects_stations(
            s_request, header_get_organization
        )

        station_list_raw_insert = StationListRaw(**{"raw_station_data": stations_csv})

        s_db.add(station_list_raw_insert)
        s_db.commit()

        header_station_measurements = header_data_template.copy()
        header_station_page = header_data_template.copy()

        projects_iter = tqdm(projects.iterrows(), total=projects.shape[0], position=0)
        for _, project in projects_iter:
            project_name = project["project_name"]
            projects_iter.set_description(_fmt_desc(f" project ({project_name})"))
            project_id = project["project_id"]

            project_insert = Project(**{"id": project_id, "project_name": project_name})

            s_db.add(project_insert)
            s_db.commit()

            stations_in_project = stations[stations["project_id"] == project_id]

            stations_iter = tqdm(
                stations_in_project.iterrows(),
                total=stations_in_project.shape[0],
                position=1,
                leave=False,
            )
            for _, station in stations_iter:
                station_name = station["station_name"]
                stations_iter.set_description(_fmt_desc(f" station ({station_name})"))
                station_id = station["station_id"]

                header_station_measurements["Referer"] = (
                    f"https://wit.fathomscientific.com/station/{station_id}/"
                )

                station_insert = Station(
                    **{
                        "id": station_id,
                        "station_name": station_name,
                        "project_id": project_id,
                        "cft_1": station["cft_1"],
                        "cft_2": station["cft_2"],
                        "cft_3": station["cft_3"],
                    }
                )

                # NOTE: commit at the end of the station loop
                s_db.add(station_insert)

                # Get the measurements and calibrations of a station
                measurements_csv, measurements, calibrations_csv, calibrations = (
                    get_station_data(
                        s_request,
                        project_id,
                        station_id,
                        header_station_measurements,
                        header_station_page,
                    )
                )

                # loop over measurements, insert each measurement and
                # download and insert each measurement_data_csv in corresponding table
                for _mi, md in tqdm(
                    measurements.iterrows(),
                    desc=_fmt_desc(" measurement at station"),
                    total=measurements.shape[0],
                    leave=False,
                    position=2,
                ):
                    measurement_data_csv = s_request.get(
                        md["download_link"], headers=header_station_measurements
                    )

                    measurement_insert = Measurement(
                        **{
                            "measurement_id": md["ID"],
                            "station_id": station_id,
                            "group_id": md["group"],
                            "datetime_start": md["Date of Q Measurement"],
                            "datetime_end": md["End time of Q Measurement"],
                            "upstream_probe": md["IsUpstream"],
                            "flow_cms": md["Flow (cms)"],
                            "uncertainty_percent": md["Measurement Uncertainty"],
                            "notes": md["Notes"],
                            "datetime_modified": md["Modified"],
                            "modified_by": md["Last Modified By"],
                            "locked_update_delete": md["Locked from Update and Delete"],
                            "locked_by": md["Locked By"],
                            "party": md["Party"],
                            "created_by": md["Created By"],
                            "stage_m": md["Stage (m)"],
                            "stage_datetime": md["Stage Time"],
                            "dl_stage_m": md["DL Stage (m)"],
                            "ref_stage_m": md["Ref Stage (m)"],
                            "type": md["Type"],
                            "filename": md["Filename"],
                            "sd_file_id": md["SDFile_ID"],
                            "sdiq_mass_nacl_kg": md["SDIQ - Mass NaCl"],
                            "sdiq_cft": md["SDIQ - CFT"],
                            "channel_name": md["Channel Name"],
                            "rating_curve_ids": md["Rating Curve ID"],
                            "probe_serial_number": md["Probe Serial Number"],
                        }
                    )
                    measurement_csv_insert = MeasurementCSVData(
                        **{
                            "measurement_id": md["ID"],
                            "csv_data": measurement_data_csv.content,
                        }
                    )

                    s_db.add(measurement_insert)
                    s_db.add(measurement_csv_insert)

                measurement_raw_insert = MeasurementRaw(
                    **{
                        "station_id": station_id,
                        "station_raw_measurement_data": measurements_csv,
                    }
                )
                s_db.add(measurement_raw_insert)

                for _cal_i, cal_d in calibrations.iterrows():
                    calibration_insert = Calibration(
                        **{
                            "id": cal_d["ID"],
                            "station_id": station_id,
                            "datetime_of_calibration": cal_d["Date of Calibration"],
                            "coeff_var_regression_r2": cal_d[
                                "Coefficient of Variation of the Calibration Regression(R^2)"
                            ],
                            "cf_t": cal_d[
                                "Temperature-adjusted Conductivity vs Concentration Regression Coefficient"
                            ],
                            "cf_t_uncertainty": cal_d["CF.T Uncertainty"],
                            "volume_distilled_water_calibration_l": cal_d[
                                "Volume of Distilled H20 used in calibration."
                            ],
                            "mass_salt_calibration_mg": cal_d[
                                "Mass of salt used in calibration."
                            ],
                            "volume_stream_water_calibration_l": cal_d[
                                "Volume of H20 from stream used in calibration."
                            ],
                            "volume_injection_calibration_solution_ml": cal_d[
                                "Volume of calibration solution injected at each step of 5-point calibration."
                            ],
                            "ec_t_step_1": cal_d["First calibration step ECT."],
                            "ec_t_step_2": cal_d["Second calibration step ECT."],
                            "ec_t_step_3": cal_d["Third calibration step ECT."],
                            "ec_t_step_4": cal_d["Fourth calibration step ECT."],
                            "ec_t_step_5": cal_d["Fifth calibration step ECT."],
                            "filename": cal_d["Filename"],
                        }
                    )

                    s_db.add(calibration_insert)

                calibration_raw_insert = CalibrationRaw(
                    **{
                        "station_id": station_id,
                        "station_raw_calibration_data": calibrations_csv,
                    }
                )
                s_db.add(calibration_raw_insert)

                # TODO refactor, see get_station_groups in web_scraping.py
                groups = [int(x) for x in set(measurements["group"]) if ~np.isnan(x)]
                group_inserts = []
                for group in groups:
                    group_csv_link = f"https://wit.fathomscientific.com/group-measurement/{group}/csv-download"
                    group_csv_data = s_request.get(
                        group_csv_link, headers=header_station_measurements
                    )

                    group_inserts.append(
                        MeasurementGroup(
                            **{"id": group, "group_summary": group_csv_data.content}
                        )
                    )

                s_db.add_all(group_inserts)

                s_db.commit()  # all data commit for station here
