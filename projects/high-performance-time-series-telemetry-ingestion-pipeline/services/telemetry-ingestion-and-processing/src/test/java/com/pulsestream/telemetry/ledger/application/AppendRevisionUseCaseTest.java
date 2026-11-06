package com.pulsestream.telemetry.ledger.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.domain.TelemetryEventKey;
import com.pulsestream.telemetry.ledger.domain.TelemetryRevision;
import com.pulsestream.telemetry.ledger.domain.TelemetryRevisionAppended;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AppendRevisionUseCaseTest {

    private static final Instant TS = Instant.parse("2024-01-01T00:00:00Z");

    @Mock
    private TelemetryLedgerRepository repository;

    @Mock
    private TelemetryRevisionEventPublisher publisher;

    private AppendRevisionUseCase useCase;
    private TelemetryEventKey key;

    @BeforeEach
    void setUp() {
        useCase = new AppendRevisionUseCase(repository, publisher);
        key = new TelemetryEventKey("device-1", "temperature", TS);
    }

    @Test
    void execute_firstSampleForKey_appendsRevisionOne() {
        when(repository.findRevisions(key)).thenReturn(List.of());
        when(repository.append(any(TelemetryRevision.class))).thenAnswer(i -> i.getArgument(0));

        TelemetryRevision result = useCase.execute(new AppendRevisionCommand(key, 21.5));

        assertThat(result.revision()).isEqualTo(1L);
    }

    @Test
    void execute_lateBackfillForExistingKey_appendsNextRevisionPreservingHistory() {
        when(repository.findRevisions(key)).thenReturn(List.of(
                new TelemetryRevision(key, 1L, 20.0), new TelemetryRevision(key, 2L, 20.5)));
        when(repository.append(any(TelemetryRevision.class))).thenAnswer(i -> i.getArgument(0));

        TelemetryRevision result = useCase.execute(new AppendRevisionCommand(key, 22.0));

        ArgumentCaptor<TelemetryRevision> captor = ArgumentCaptor.forClass(TelemetryRevision.class);
        verify(repository).append(captor.capture());
        assertThat(result.revision()).isEqualTo(3L);
        assertThat(captor.getValue().revision()).isEqualTo(3L);
    }

    @Test
    void execute_successfulAppend_publishesTelemetryRevisionAppended() {
        when(repository.findRevisions(key)).thenReturn(List.of(new TelemetryRevision(key, 1L, 20.0)));
        when(repository.append(any(TelemetryRevision.class))).thenAnswer(i -> i.getArgument(0));

        useCase.execute(new AppendRevisionCommand(key, 22.0));

        ArgumentCaptor<TelemetryRevisionAppended> captor =
                ArgumentCaptor.forClass(TelemetryRevisionAppended.class);
        verify(publisher).publish(captor.capture());
        assertThat(captor.getValue().key()).isEqualTo(key);
        assertThat(captor.getValue().revision()).isEqualTo(2L);
    }

    @Test
    void execute_repositoryFails_propagatesErrorAndPublishesNothing() {
        when(repository.findRevisions(key)).thenReturn(List.of());
        when(repository.append(any(TelemetryRevision.class)))
                .thenThrow(new IllegalStateException("storage down"));

        assertThatThrownBy(() -> useCase.execute(new AppendRevisionCommand(key, 21.5)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("storage down");
        verify(publisher, never()).publish(any());
    }
}
