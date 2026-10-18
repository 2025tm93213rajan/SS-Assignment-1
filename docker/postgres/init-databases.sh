#!/bin/bash
set -e

function create_user_and_database() {
	local database=$1
	local user=$2
	local password=$3
	echo "Initializing user '$user' and database '$database'..."
	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
	    DO \$\$
	    BEGIN
	        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$user') THEN
	            CREATE USER $user WITH ENCRYPTED PASSWORD '$password';
	        END IF;
	    END
	    \$\$;
	    SELECT 'CREATE DATABASE $database OWNER $user'
	    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')\gexec
	    GRANT ALL PRIVILEGES ON DATABASE $database TO $user;
EOSQL
}

create_user_and_database "inventory_db" "inventory_user" "inventory_pass"
create_user_and_database "booking_db" "booking_user" "booking_pass"
create_user_and_database "ticketing_db" "ticketing_user" "ticketing_pass"
echo "PostgreSQL multi-database initialization complete."
