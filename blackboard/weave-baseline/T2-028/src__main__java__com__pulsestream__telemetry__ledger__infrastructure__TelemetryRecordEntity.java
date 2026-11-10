package com.pulsestream.telemetry.ledger.infrastructure;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Version;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("ledger.telemetry_records")
public class TelemetryRecordEntity {

    @Id
    private UUID id;

    @Column("device_id")
    private String deviceId;

    private String metric;

    private double value;

    @Column("t_device")
    private Instant tDevice;

    @Column("t_ingress")
    private Instant tIngress;

    @Column("validation_status")
    private String validationStatus;

    private int revision;

    @Column("supersedes_id")
    private UUID supersedesId;

    @Version
    private Integer version;

    public TelemetryRecordEntity() {
    }

    public static TelemetryRecordEntity fromDomain(TelemetryRecord record) {
        Objects.requireNonNull(record, "record must not be null");
        TelemetryRecordEntity entity = new TelemetryRecordEntity();
        entity.id = record.id();
        entity.deviceId = record.deviceId();
        entity.metric = record.metric();
        entity.value = record.value();
        entity.tDevice = record.tDevice();
        entity.tIngress = record.tIngress();
        entity.validationStatus = record.validationStatus();
        entity.revision = record.revision();
        entity.supersedesId = record.supersedesId();
        return entity;
    }

    public TelemetryRecord toDomain() {
        return new TelemetryRecord(id, deviceId, metric, value, tDevice, tIngress, validationStatus, revision, supersedesId);
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getDeviceId() {
        return deviceId;
    }

    public void setDeviceId(String deviceId) {
        this.deviceId = deviceId;
    }

    public String getMetric() {
        return metric;
    }

    public void setMetric(String metric) {
        this.metric = metric;
    }

    public double getValue() {
        return value;
    }

    public void setValue(double value) {
        this.value = value;
    }

    public Instant getTDevice() {
        return tDevice;
    }

    public void setTDevice(Instant tDevice) {
        this.tDevice = tDevice;
    }

    public Instant getTIngress() {
        return tIngress;
    }

    public void setTIngress(Instant tIngress) {
        this.tIngress = tIngress;
    }

    public String getValidationStatus() {
        return validationStatus;
    }

    public void setValidationStatus(String validationStatus) {
        this.validationStatus = validationStatus;
    }

    public int getRevision() {
        return revision;
    }

    public void setRevision(int revision) {
        this.revision = revision;
    }

    public UUID getSupersedesId() {
        return supersedesId;
    }

    public void setSupersedesId(UUID supersedesId) {
        this.supersedesId = supersedesId;
    }

    public Integer getVersion() {
        return version;
    }

    public void setVersion(Integer version) {
        this.version = version;
    }
}
