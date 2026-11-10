package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.application.port.out.TelemetryLedgerRepository;
import com.pulsestream.telemetry.ledger.domain.TelemetryRecord;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class R2dbcTelemetryLedgerRepositoryTest {

    private static final UUID ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_ID = UUID.fromString("00000000-0000-0000-0000-000000000002");
    private static final Instant T_DEVICE = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant T_TO = Instant.parse("2024-01-02T00:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T00:00:01Z");

    @Mock
    private TelemetryRecordR2dbcRepository repository;

    @Mock
    private R2dbcEntityTemplate template;

    private TelemetryLedgerRepository adapter;

    @BeforeEach
    void setUp() {
        adapter = new R2dbcTelemetryLedgerRepository(repository, template);
    }

    private static TelemetryRecord original() {
        return new TelemetryRecord(ID, "dev-1", "temp", 21.5, T_DEVICE, T_INGRESS, "VALID", 0, null);
    }

    private static TelemetryRecord revision() {
        return new TelemetryRecord(OTHER_ID, "dev-1", "temp", 22.5, T_DEVICE, T_INGRESS, "VALID", 1, ID);
    }

    @Test
    void class_isAnnotatedAsRepositoryAndImplementsPort() {
        assertThat(R2dbcTelemetryLedgerRepository.class.isAnnotationPresent(Repository.class)).isTrue();
        assertThat(TelemetryLedgerRepository.class).isAssignableFrom(R2dbcTelemetryLedgerRepository.class);
    }

    @Test
    void append_validRecord_insertsEntityAndReturnsDomainRecord() {
        TelemetryRecord record = original();
        when(template.insert(any(TelemetryRecordEntity.class)))
                .thenAnswer(inv -> Mono.just(inv.<TelemetryRecordEntity>getArgument(0)));

        StepVerifier.create(adapter.append(record)).expectNext(record).verifyComplete();

        ArgumentCaptor<TelemetryRecordEntity> captor = ArgumentCaptor.forClass(TelemetryRecordEntity.class);
        verify(template).insert(captor.capture());
        assertThat(captor.getValue().toDomain()).isEqualTo(record);
        verifyNoMoreInteractions(repository);
    }

    @Test
    void append_revisionRecord_preservesRevisionAndSupersedesId() {
        TelemetryRecord record = revision();
        when(template.insert(any(TelemetryRecordEntity.class)))
                .thenAnswer(inv -> Mono.just(inv.<TelemetryRecordEntity>getArgument(0)));

        StepVerifier.create(adapter.append(record))
                .assertNext(saved -> {
                    assertThat(saved.revision()).isEqualTo(1);
                    assertThat(saved.supersedesId()).isEqualTo(ID);
                })
                .verifyComplete();
    }

    @Test
    void append_templateFails_propagatesError() {
        when(template.insert(any(TelemetryRecordEntity.class)))
                .thenReturn(Mono.error(new IllegalStateException("trigger rejected")));

        StepVerifier.create(adapter.append(original()))
                .expectErrorMessage("trigger rejected")
                .verify();
    }

    @Test
    void findHistory_rangeGiven_delegatesAndMapsToDomain() {
        when(repository.findHistory("dev-1", T_DEVICE, T_TO))
                .thenReturn(Flux.just(TelemetryRecordEntity.fromDomain(original()),
                        TelemetryRecordEntity.fromDomain(revision())));

        StepVerifier.create(adapter.findHistory("dev-1", T_DEVICE, T_TO))
                .expectNext(original(), revision())
                .verifyComplete();
    }

    @Test
    void findHistory_noRows_completesEmpty() {
        when(repository.findHistory("dev-1", T_DEVICE, T_TO)).thenReturn(Flux.empty());

        StepVerifier.create(adapter.findHistory("dev-1", T_DEVICE, T_TO)).verifyComplete();
    }

    @Test
    void findLatestRevision_rowExists_returnsMappedRecord() {
        when(repository.findLatestRevision("dev-1", "temp", T_DEVICE))
                .thenReturn(Mono.just(TelemetryRecordEntity.fromDomain(revision())));

        StepVerifier.create(adapter.findLatestRevision("dev-1", "temp", T_DEVICE))
                .expectNext(revision())
                .verifyComplete();
    }

    @Test
    void findLatestRevision_noRow_completesEmpty() {
        when(repository.findLatestRevision("dev-1", "temp", T_DEVICE)).thenReturn(Mono.empty());

        StepVerifier.create(adapter.findLatestRevision("dev-1", "temp", T_DEVICE)).verifyComplete();
    }

    @Test
    void findRevisionChain_rowsExist_delegatesAndKeepsOrder() {
        when(repository.findRevisionChain("dev-1", "temp", T_DEVICE))
                .thenReturn(Flux.just(TelemetryRecordEntity.fromDomain(original()),
                        TelemetryRecordEntity.fromDomain(revision())));

        StepVerifier.create(adapter.findRevisionChain("dev-1", "temp", T_DEVICE))
                .expectNext(original(), revision())
                .verifyComplete();
    }

    @Test
    void findRevisionChain_repositoryFails_propagatesError() {
        when(repository.findRevisionChain("dev-1", "temp", T_DEVICE))
                .thenReturn(Flux.error(new IllegalStateException("db down")));

        StepVerifier.create(adapter.findRevisionChain("dev-1", "temp", T_DEVICE))
                .expectErrorMessage("db down")
                .verify();
    }
}
