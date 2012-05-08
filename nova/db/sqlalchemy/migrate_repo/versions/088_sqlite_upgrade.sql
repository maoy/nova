BEGIN TRANSACTION;
    CREATE TEMPORARY TABLE block_device_mapping_backup (
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted BOOLEAN,
        id INTEGER NOT NULL,
        instance_id INTEGER NOT NULL,
        device_name VARCHAR(255) NOT NULL,
        delete_on_termination BOOLEAN,
        virtual_name VARCHAR(255),
        snapshot_id INTEGER,
        volume_id INTEGER,
        volume_size INTEGER,
        no_device BOOLEAN,
        connection_info TEXT,
        instance_uuid VARCHAR(36),
        PRIMARY KEY (id),
        FOREIGN KEY(snapshot_id) REFERENCES snapshots (id),
        CHECK (deleted IN (0, 1)),
        CHECK (delete_on_termination IN (0, 1)),
        CHECK (no_device IN (0, 1)),
        FOREIGN KEY(volume_id) REFERENCES volumes (id),
        FOREIGN KEY(instance_id) REFERENCES instances (id)
    );

    INSERT INTO block_device_mapping_backup
        SELECT created_at,
               updated_at,
               deleted_at,
               deleted,
               id,
               instance_id,
               device_name,
               delete_on_termination,
               virtual_name,
               snapshot_id,
               volume_id,
               volume_size,
               no_device,
               connection_info,
               NULL
        FROM block_device_mapping;

    UPDATE block_device_mapping_backup
        SET instance_uuid=
            (SELECT uuid
                 FROM instances
                 WHERE block_device_mapping_backup.instance_id = instances.id
    );

    DROP TABLE block_device_mapping;

    CREATE TABLE block_device_mapping (
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted BOOLEAN,
        id INTEGER NOT NULL,
        device_name VARCHAR(255) NOT NULL,
        delete_on_termination BOOLEAN,
        virtual_name VARCHAR(255),
        snapshot_id INTEGER,
        volume_id INTEGER,
        volume_size INTEGER,
        no_device BOOLEAN,
        connection_info TEXT,
        instance_uuid VARCHAR(36),
        PRIMARY KEY (id),
        FOREIGN KEY(snapshot_id) REFERENCES snapshots (id),
        CHECK (deleted IN (0, 1)),
        CHECK (delete_on_termination IN (0, 1)),
        CHECK (no_device IN (0, 1)),
        FOREIGN KEY(volume_id) REFERENCES volumes (id),
        FOREIGN KEY(instance_uuid) REFERENCES instances (uuid)
    );

    INSERT INTO block_device_mapping
        SELECT created_at,
               updated_at,
               deleted_at,
               deleted,
               id,
               device_name,
               delete_on_termination,
               virtual_name,
               snapshot_id,
               volume_id,
               volume_size,
               no_device,
               connection_info,
               instance_uuid
        FROM block_device_mapping_backup;

    DROP TABLE block_device_mapping_backup;

    CREATE TABLE tasks (
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted BOOLEAN,
        id INTEGER NOT NULL,
        depth INTEGER NOT NULL,
        state VARCHAR(255),
        context VARCHAR(255),
        execlog TEXT,
        info TEXT,
        PRIMARY KEY (id)
    );

    CREATE TABLE locks (
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted BOOLEAN,
        id INTEGER NOT NULL,
        name VARCHAR(255),
        tid INTEGER,
        style INTEGER,
        PRIMARY KEY (id)
    );


COMMIT;
