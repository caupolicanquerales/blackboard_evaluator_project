package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.domain.EventRevision;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.r2dbc.core.DatabaseClient.GenericExecuteSpec;
import org.springframework.r2dbc.core.FetchSpec;
import org.springframework.r2dbc.core.RowsFetchSpec;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@SuppressWarnings({"unchecked", "rawtypes"})
class R2dbcEventRevisionRepositoryTest {

    private static final Instant FROM = Instant.parse("2025-01-01T00:00:00Z");
    private static final Instant TO = Instant.parse("2025-01-02T00:00:00Z");

    private DatabaseClient client;
    private GenericExecuteSpec spec;
    private R2dbcEventRevisionRepository repository;

    @BeforeEach
    void setUp() {
        client = mock(DatabaseClient.class);
        spec = mock(GenericExecuteSpec.class, Mockito.RETURNS_SELF);
        when(client.sql(anyString())).thenReturn(spec);
        repository = new R2dbcEventRevisionRepository(client);
    }

    private EventRevision revision(long number) {
        return new EventRevision("device-1", "temperature", FROM.plusSeconds(60), number, 21.5);
    }

    private void stubWrite(Mono<Void> result) {
        FetchSpec fetch = mock(FetchSpec.class);
        when(fetch.rowsUpdated()).thenReturn(result.then(Mono.just(1L)));
        when(spec.fetch()).thenReturn(fetch);
        when(spec.then()).thenReturn(result);
    }

    private String capturedSql() {
        ArgumentCaptor<String> sql = ArgumentCaptor.forClass(String.class);
        Mockito.verify(client).sql(sql.capture());
        return sql.getValue().toLowerCase();
    }

    @Test
    void append_validRevision_insertsIntoEventRevisionsOnly() {
        stubWrite(Mono.empty());

        StepVerifier.create(repository.append(revision(1))).expectNextCount(1).verifyComplete();

        assertThat(capturedSql())
                .contains("insert into telemetry.event_revisions")
                .doesNotContain("update ")
                .doesNotContain("delete ");
    }

    @Test
    void append_duplicateKey_surfacesError() {
        stubWrite(Mono.error(new DuplicateKeyException("duplicate")));

        StepVerifier.create(repository.append(revision(1)))
                .expectError(DuplicateKeyException.class)
                .verify();
    }

    @Test
    void history_deviceMetricAndRange_queriesOrderedByRevision() {
        RowsFetchSpec rows = mock(RowsFetchSpec.class);
        when(rows.all()).thenReturn(Flux.just(revision(1), revision(2)));
        when(spec.map(Mockito.any(java.util.function.BiFunction.class))).thenReturn(rows);

        StepVerifier.create(repository.history("device-1", "temperature", FROM, TO))
                .expectNext(revision(1), revision(2))
                .verifyComplete();

        assertThat(capturedSql())
                .contains("telemetry.event_revisions")
                .contains("order by")
                .contains("revision")
                .doesNotContain("update ")
                .doesNotContain("delete ");
    }

    @Test
    void latest_existingEvent_returnsHighestRevision() {
        RowsFetchSpec rows = mock(RowsFetchSpec.class);
        when(rows.one()).thenReturn(Mono.just(revision(3)));
        when(rows.first()).thenReturn(Mono.just(revision(3)));
        when(spec.map(Mockito.any(java.util.function.BiFunction.class))).thenReturn(rows);

        StepVerifier.create(repository.latest("device-1", "temperature", FROM.plusSeconds(60)))
                .expectNext(revision(3))
                .verifyComplete();

        assertThat(capturedSql()).contains("order by").contains("revision desc");
    }
}
