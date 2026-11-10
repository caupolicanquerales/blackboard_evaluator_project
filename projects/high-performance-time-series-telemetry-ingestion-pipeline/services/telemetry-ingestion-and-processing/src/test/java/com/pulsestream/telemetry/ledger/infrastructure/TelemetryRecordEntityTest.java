package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.Version;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

class TelemetryRecordEntityTest {

    private static final UUID ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID PREVIOUS_ID = UUID.fromString("00000000-0000-0000-0000-000000000002");
    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:01.123456Z");

    private static TelemetryRecord originalRecord() {
        return new TelemetryRecord(ID, "dev-1", "temperature", 21.5, T_DEVICE, T_INGRESS, "VALID", 0, null);
    }

    private static TelemetryRecord revisedRecord() {
        return new TelemetryRecord(ID, "dev-1", "temperature", 22.5, T_DEVICE, T_INGRESS, "CORRECTED", 2, PREVIOUS_ID);
    }

    @Test
    void entity_class_isMappedToLedgerTelemetryRecordsTable() {
        Table table = TelemetryRecordEntity.class.getAnnotation(Table.class);

        assertThat(table).isNotNull();
        assertThat(table.value()).isEqualTo("ledger.telemetry_records");
    }

    @Test
    void entity_fields_carryIdVersionAndColumnMappings() throws NoSuchFieldException {
        assertThat(TelemetryRecordEntity.class.getDeclaredField("id").isAnnotationPresent(Id.class)).isTrue();
        assertThat(TelemetryRecordEntity.class.getDeclaredField("version").isAnnotationPresent(Version.class))
                .isTrue();
        assertThat(TelemetryRecordEntity.class.getDeclaredField("deviceId").getAnnotation(Column.class).value())
                .isEqualTo("device_id");
        assertThat(TelemetryRecordEntity.class.getDeclaredField("tDevice").getAnnotation(Column.class).value())
                .isEqualTo("t_device");
        assertThat(TelemetryRecordEntity.class.getDeclaredField("tIngress").getAnnotation(Column.class).value())
                .isEqualTo("t_ingress");
        assertThat(TelemetryRecordEntity.class.getDeclaredField("validationStatus")
                .getAnnotation(Column.class).value()).isEqualTo("validation_status");
        assertThat(TelemetryRecordEntity.class.getDeclaredField("supersedesId").getAnnotation(Column.class).value())
                .isEqualTo("supersedes_id");
    }

    @Test
    void fromDomain_originalRecord_copiesAllFields() {
        TelemetryRecordEntity entity = TelemetryRecordEntity.fromDomain(originalRecord());

        assertThat(entity.getId()).isEqualTo(ID);
        assertThat(entity.getDeviceId()).isEqualTo("dev-1");
        assertThat(entity.getMetric()).isEqualTo("temperature");
        assertThat(entity.getValue()).isEqualTo(21.5);
        assertThat(entity.getTDevice()).isEqualTo(T_DEVICE);
        assertThat(entity.getTIngress()).isEqualTo(T_INGRESS);
        assertThat(entity.getValidationStatus()).isEqualTo("VALID");
        assertThat(entity.getRevision()).isZero();
        assertThat(entity.getSupersedesId()).isNull();
    }

    @Test
    void fromDomain_anyRecord_leavesVersionNullSoSpringDataInserts() {
        TelemetryRecordEntity entity = TelemetryRecordEntity.fromDomain(originalRecord());

        assertThat(entity.getVersion()).isNull();
    }

    @Test
    void fromDomain_revisedRecord_keepsRevisionAndSupersedesId() {
        TelemetryRecordEntity entity = TelemetryRecordEntity.fromDomain(revisedRecord());

        assertThat(entity.getRevision()).isEqualTo(2);
        assertThat(entity.getSupersedesId()).isEqualTo(PREVIOUS_ID);
    }

    @Test
    void toDomain_afterFromDomain_roundTripsOriginalWithoutLoss() {
        TelemetryRecord result = TelemetryRecordEntity.fromDomain(originalRecord()).toDomain();

        assertThat(result).isEqualTo(originalRecord());
    }

    @Test
    void toDomain_afterFromDomain_roundTripsRevisionWithoutLoss() {
        TelemetryRecord result = TelemetryRecordEntity.fromDomain(revisedRecord()).toDomain();

        assertThat(result).isEqualTo(revisedRecord());
    }

    @Test
    void toDomain_entityWithVersionSet_ignoresVersion() {
        TelemetryRecordEntity entity = TelemetryRecordEntity.fromDomain(originalRecord());
        entity.setVersion(3);

        assertThat(entity.toDomain()).isEqualTo(originalRecord());
    }

    @Test
    void toDomain_entityWithInconsistentRevision_throwsDomainInvariantViolation() {
        TelemetryRecordEntity entity = TelemetryRecordEntity.fromDomain(originalRecord());
        entity.setRevision(1);

        assertThatThrownBy(entity::toDomain).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void fromDomain_nullRecord_throwsNullPointerException() {
        assertThatThrownBy(() -> TelemetryRecordEntity.fromDomain(null))
                .isInstanceOf(NullPointerException.class);
    }
}
