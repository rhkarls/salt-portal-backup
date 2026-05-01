# SPDX-FileCopyrightText: 2024-present Reinert Huseby Karlsen <rhkarls@proton.me>
#
# SPDX-License-Identifier: BSD-3-Clause

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("salt-portal-backup")
except PackageNotFoundError:
    __version__ = "unknown"

from .salt_portal import run_backup as run_backup
