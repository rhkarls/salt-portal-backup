
"""
Example calling the python code for performing backup

Note: it is not recommend storing login credetials in python code
Use, for example, environmental variables and .env files instead
"""

from salt_portal_backup import run_backup

# without providing path to the database file
# backup will be stored in the user home directory
# with name salt_portal_yyyymmdd_hhmmss.db where yyyymmdd_hhmmss
# is the current date and time
run_backup(username='myusername', password='mypassword')

# provide location for the backup adding database_path keyword
# example below will create the my_backup.db database in the current
# working directory of the python session
run_backup(username='myusername', password='mypassword', 
           database_path='my_backup.db')