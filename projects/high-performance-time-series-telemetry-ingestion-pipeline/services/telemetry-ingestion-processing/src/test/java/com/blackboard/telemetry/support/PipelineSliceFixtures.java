package com.blackboard.telemetry.support;
import java.util.Set;

import reactor.core.publisher.Mono;
import org.springframework.r2dbc.core.DatabaseClient;

public class PipelineSliceFixtures {

    private static final Set<String> COUNTABLE_TABLES = Set.of("telemetry_sample", "event_revision", "audit_trail");

    public static Mono<Long> countRows(DatabaseClient client, String table) {
        if (!COUNTABLE_TABLES.contains(table)) {
            throw new IllegalArgumentException("Unsupported table: " + table);
        }
        return client.sql("SELECT COUNT(*) AS c FROM " + table).map((row, meta) -> row.get(0, Long.class)).one();
    }

    public static String packetJson(String deviceId, String sourceKind, String metric, long tDeviceEpochMillis, double value) {
        return "{\"deviceId\":\"" + deviceId + "\",\"sourceKind\":\"" + sourceKind + "\",\"samples\":[{\"metric\":\"" + metric + "\",\"tDeviceEpochMillis\":" + tDeviceEpochMillis + ",\"value\":" + value + "}]}";
    }
}
