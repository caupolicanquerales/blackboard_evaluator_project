package com.pulsestream.telemetry.ledger.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.data.r2dbc.repository.Query;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

class TelemetryRecordR2dbcRepositoryTest {

    private static final Class<?> REPOSITORY = TelemetryRecordR2dbcRepository.class;

    private static Method method(String name) {
        return Arrays.stream(REPOSITORY.getDeclaredMethods())
                .filter(m -> m.getName().equals(name))
                .findFirst()
                .orElseThrow(() -> new AssertionError("Missing repository method " + name));
    }

    private static String sql(String name) {
        Query query = method(name).getAnnotation(Query.class);
        assertThat(query).as("@Query on " + name).isNotNull();
        return query.value().replaceAll("\\s+", " ").toUpperCase();
    }

    @Test
    void repository_declaration_isInterfaceExtendingReactiveCrudRepository() {
        assertThat(REPOSITORY.isInterface()).isTrue();
        assertThat(ReactiveCrudRepository.class).isAssignableFrom(REPOSITORY);
    }

    @Test
    void repository_declaration_bindsEntityAndUuidTypeArguments() {
        String generics = Arrays.toString(REPOSITORY.getGenericInterfaces());

        assertThat(generics)
                .contains(TelemetryRecordEntity.class.getName())
                .contains(UUID.class.getName());
    }

    @Test
    void findHistory_declaration_returnsFluxOfEntitiesWithThreeParameters() {
        Method m = method("findHistory");

        assertThat(m.getReturnType()).isEqualTo(Flux.class);
        assertThat(m.getParameterCount()).isEqualTo(3);
        assertThat(m.getGenericReturnType().getTypeName()).contains(TelemetryRecordEntity.class.getName());
    }

    @Test
    void findHistory_query_ordersByTDeviceThenRevision() {
        assertThat(sql("findHistory")).contains("ORDER BY T_DEVICE, REVISION");
    }

    @Test
    void findHistory_query_usesHalfOpenRangeOnTDevice() {
        assertThat(sql("findHistory"))
                .contains("LEDGER.TELEMETRY_RECORDS")
                .contains("DEVICE_ID = :")
                .contains("T_DEVICE >= :")
                .contains("T_DEVICE < :");
    }

    @Test
    void findLatestRevision_declaration_returnsMonoOfEntityWithThreeParameters() {
        Method m = method("findLatestRevision");

        assertThat(m.getReturnType()).isEqualTo(Mono.class);
        assertThat(m.getParameterCount()).isEqualTo(3);
        assertThat(m.getGenericReturnType().getTypeName()).contains(TelemetryRecordEntity.class.getName());
    }

    @Test
    void findLatestRevision_query_ordersByRevisionDescLimitOne() {
        assertThat(sql("findLatestRevision")).contains("ORDER BY REVISION DESC").contains("LIMIT 1");
    }

    @Test
    void findLatestRevision_query_filtersByDeviceMetricAndTDevice() {
        assertThat(sql("findLatestRevision"))
                .contains("DEVICE_ID = :")
                .contains("METRIC = :")
                .contains("T_DEVICE = :");
    }

    @Test
    void findRevisionChain_declaration_returnsFluxOfEntitiesWithThreeParameters() {
        Method m = method("findRevisionChain");

        assertThat(m.getReturnType()).isEqualTo(Flux.class);
        assertThat(m.getParameterCount()).isEqualTo(3);
        assertThat(m.getGenericReturnType().getTypeName()).contains(TelemetryRecordEntity.class.getName());
    }

    @Test
    void findRevisionChain_query_ordersByRevisionAscending() {
        String query = sql("findRevisionChain");

        assertThat(query).contains("ORDER BY REVISION").doesNotContain("DESC");
    }

    @Test
    void findRevisionChain_query_filtersByDeviceMetricAndTDevice() {
        assertThat(sql("findRevisionChain"))
                .contains("DEVICE_ID = :")
                .contains("METRIC = :")
                .contains("T_DEVICE = :");
    }

    @ParameterizedTest
    @ValueSource(strings = {"findHistory", "findLatestRevision", "findRevisionChain"})
    void queries_allCustomMethods_areReadOnlySelectsOnLedgerTable(String name) {
        String query = sql(name);

        assertThat(query)
                .startsWith("SELECT")
                .contains("FROM LEDGER.TELEMETRY_RECORDS")
                .doesNotContain("DELETE")
                .doesNotContain("UPDATE ");
    }

    @Test
    void repository_declaration_declaresOnlyTheThreeQueryMethods() {
        Stream<String> names = Arrays.stream(REPOSITORY.getDeclaredMethods()).map(Method::getName);

        assertThat(names).containsExactlyInAnyOrder("findHistory", "findLatestRevision", "findRevisionChain");
    }
}
