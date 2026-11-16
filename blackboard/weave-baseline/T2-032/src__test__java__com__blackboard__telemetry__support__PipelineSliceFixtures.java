import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.publisher.Mono;

public class PipelineSliceFixtures {

    static public Mono<Long> countRows(DatabaseClient client, String table) {
        if (!"telemetry_sample".equals(table) && !"event_revision".equals(table) && !"audit_trail".equals(table)) {
            throw new IllegalArgumentException("Unsupported table: " + table);
        }
        return client.sql("SELECT COUNT(*) FROM " + table).map(row -> row.get(0, Long.class)).one();
    }
}
