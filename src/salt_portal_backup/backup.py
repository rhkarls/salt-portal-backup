# SPDX-FileCopyrightText: 2024-present Reinert Huseby Karlsen <rhkarls@proton.me>
#
# SPDX-License-Identifier: BSD-3-Clause

import click

from salt_portal_backup.salt_portal import run_backup
from salt_portal_backup.__about__ import __version__


@click.command(
    help=(
        "Backup projects, stations, calibrations and measurements from Salt Portal "
        "to a SQLite database."
    )
)
@click.option(
    "-u",
    "--username",
    prompt="Salt Portal username",
    help="The Salt Portal login username. Will be prompted if not provided.",
)
@click.option(
    "-p",
    "--password",
    prompt="Salt Portal password",
    hide_input=True,
    help="The Salt Portal login password. Will be prompted if not provided.",
)
@click.option(
    "-o",
    "--output_database",
    default=None,
    help=(
        "Path to the SQLite database to store the backup in. The database is created if not "
        "excisting, and it is recommended to use a new database for each backup. "
        "If not provided, the database will be created in the users home folder and named with "
        "the current date and time time."
    ),
)
@click.version_option(version=__version__, prog_name="Salt Portal Backup")
def main(username, password, output_database):
    run_backup(username, password, output_database)


if __name__ == "__main__":
    main()
