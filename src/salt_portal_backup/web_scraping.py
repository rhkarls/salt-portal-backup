# SPDX-FileCopyrightText: 2024-present Reinert Huseby Karlsen <rhkarls@proton.me>
#
# SPDX-License-Identifier: BSD-3-Clause

import re
from io import BytesIO

from bs4 import BeautifulSoup as bs
import pandas as pd
# import polars as pl
import numpy as np

URL_LOGIN = "https://wit.fathomscientific.com/accounts/login/"

header_login = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://wit.fathomscientific.com/accounts/login/?next=/",
    "Content-Type": "application/x-www-form-urlencoded",
    "Content-Length": "134",
    "Origin": "https://wit.fathomscientific.com",
    "DNT": "1",
    "Connection": "keep-alive",
    "Cookie": "csrftoken={token}",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

header_data_template = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "{referer}",
    "DNT": "1",
    "Connection": "keep-alive",
    "Cookie": "csrftoken={token}",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}


def login_salt_portal(s_request, session_token, username, password):
    header_login["Cookie"] = header_login["Cookie"].format(token=session_token)
    login_payload = {
        "_method": "login",
        "csrfmiddlewaretoken": session_token,
        "login": username,
        "password": password,
        "next": "/",
    }
    return s_request.post(URL_LOGIN, data=login_payload, headers=header_login)


def get_projects_stations(s_request, header_organization):
    """ Retrieve the station csv file from SP, which also contains project information
    """
    
    header_organization["Referer"] = "https://wit.fathomscientific.com/"
    station_csv = s_request.get(
        "https://wit.fathomscientific.com/station-cfts/", headers=header_organization
    )

    station_csv_header = b"station_name,station_id,project_name,project_id,cft_1,cft_2,cft_3\r\n"
    stations = pd.read_csv(BytesIO(station_csv_header + station_csv.content))
    # stations_pl = pl.read_csv(BytesIO(station_csv_header + station_csv.content))
   
    projects = stations[["project_name", "project_id"]].drop_duplicates()
    # projects_pl = stations_pl[["project_name", "project_id"]].unique()

    return projects, stations, station_csv.content


def get_station_data(
    s_request, project_id, station_id, header_station_measurements, header_station_page
):
    """ Retrieve measurement and calibration info and data for a specific station
    """

    calibrations_csv, calibrations = get_station_calibrations(
        s_request, project_id, station_id, header_station_measurements, header_station_page
    )
    measurements_csv, measurements = get_station_measurements(
        s_request, project_id, station_id, header_station_measurements, header_station_page
    )

    return measurements_csv, measurements, calibrations_csv, calibrations


def get_station_calibrations(
    s_request, project_id, station_id, header_station_measurements, header_station_page
):
    calibrations_csv = s_request.get(
        f"https://wit.fathomscientific.com/station/{station_id}/calibrations",
        headers=header_station_measurements,
    )

    calibrations = pd.read_csv(BytesIO(calibrations_csv.content))
    calibrations["station_id"] = station_id

    if calibrations.size == 0:
        return calibrations_csv.content, calibrations

    # get calibration id, insert to calibrations dataframe 
    # matching on order and datetime intead. If this causes problems and raises
    # the Exception below, also include match on filename.
    calibrations["ID"] = pd.array([pd.NA] * calibrations.shape[0], dtype="Int64")

    header_station_page["Referer"] = f"https://wit.fathomscientific.com/project/{project_id}/"

    station_page_get = s_request.get(
        f"https://wit.fathomscientific.com/station/{station_id}/", headers=header_station_page
    )

    station_html = bs(station_page_get.text, "html.parser")

    table_2 = station_html.find("table", id="table_2")
    for i_row, row in enumerate(table_2.tbody.find_all("tr")):
        columns = row.find_all("td")
        for td in columns:
            td_links = td.find_all("a")
            if len(td_links) > 0:
                match_upd = re.search(r"/calibration/(\d+)/update", td_links[0]["href"])
                calibration_id = int(match_upd.group(1))

                html_calib_datetime = columns[0].string
                # the html table does not round the time, just truncates the datetime str so
                # e.g. 17:32:59 -> 17:32
                table_calib_datetime = calibrations.loc[i_row, "Date of Calibration"][
                    : len(html_calib_datetime)
                ]

                if html_calib_datetime == table_calib_datetime:
                    calibrations.loc[i_row, "ID"] = calibration_id
                else:
                    raise Exception("Calibration id - no match on datetime")

    return calibrations_csv.content, calibrations


def get_station_measurements(
    s_request, project_id, station_id, header_station_measurements, header_station_page
):
    measurements_csv = s_request.get(
        f"https://wit.fathomscientific.com/station/{station_id}/measurements",
        headers=header_station_measurements,
    )

    measurements = pd.read_csv(BytesIO(measurements_csv.content))
    measurements["station_id"] = station_id

    download_base = "https://wit.fathomscientific.com"
    measurements["download_link"] = None

    header_station_page["Referer"] = f"https://wit.fathomscientific.com/project/{project_id}/"

    station_page_get = s_request.get(
        f"https://wit.fathomscientific.com/station/{station_id}/", headers=header_station_page
    )

    station_html = bs(station_page_get.text, "html.parser")
    table_1 = station_html.find("table", id="table_1")

    if measurements.size == 0:
        return measurements_csv.content, measurements

    # Get download link and add to measurements
    for row in table_1.tbody.find_all("tr"):
        # Find all data for each column
        columns = row.find_all("td")
        for td in columns:
            td_links = td.find_all("a")
            if len(td_links) > 0:  # has link(s)
                for td_link in td_links:
                    if "download" in td_link["href"]:
                        csv_dl_partial_link = td_link["href"]

                        match = re.search(r"/measurement/(\d+)/update", td_links[0]["href"])
                        measurement_id = int(match.group(1))

                        measurements.loc[measurements["ID"] == measurement_id, "download_link"] = (
                            download_base + csv_dl_partial_link
                        )

    return measurements_csv.content, measurements


def get_station_groups(s, header_station_measurements, measurements):
    groups = [int(x) for x in set(measurements["group"]) if ~np.isnan(x)]
    for group in groups:
        group_csv_link = f"https://wit.fathomscientific.com/group-measurement/{group}/csv-download"
        group_csv_data = s.get(group_csv_link, headers=header_station_measurements)

    # don't need the dataframe where, csv data is not returned with a fixed strucutre
    # group_df = pd.read_csv(BytesIO(group_csv_data.content), skiprows=2)

    return group_csv_data
