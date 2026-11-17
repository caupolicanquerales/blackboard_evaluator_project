package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;
import org.springframework.r2dbc.core.DatabaseClient;

@SpringBootTest
class ApplicationYmlConfigTest {

    private static List<PropertySource<?>> documents;

    @Autowired
    private Environment environment;

    @Autowired
    private DatabaseClient db;

    @BeforeAll
    static void load() throws IOException {
        documents = new YamlPropertySourceLoader().load("application", new ClassPathResource("application.yml"));
    }

    private static Object property(String path) {
        return documents.get(0).getProperty(path);
    }

    static Stream<Arguments> literals() {
        return Stream.of(
                Arguments.of("telemetry.reorder-window-seconds", "60"),
                Arguments.of("telemetry.buffer-capacity", "1024"),
                Arguments.of("telemetry.heart-rate-min", "30"),
                Arguments.of("telemetry.heart-rate-max", "240"),
                Arguments.of("telemetry.power-min", "0"),
                Arguments.of("telemetry.power-max", "2500"),
                Arguments.of("telemetry.cadence-min", "0"),
                Arguments.of("telemetry.cadence-max", "220"),
                Arguments.of("telemetry.swim-pace-min-exclusive", "45"),
                Arguments.of("spring.application.name", "telemetry-ingestion-processing"),
                Arguments.of("spring.r2dbc.url", "r2dbc:h2:mem:///telemetry;DB_CLOSE_DELAY=-1"),
                Arguments.of("spring.r2dbc.username", "sa"),
                Arguments.of("spring.r2dbc.password", ""),
                Arguments.of("spring.flyway.enabled", "true"),
                Arguments.of("spring.flyway.url", "jdbc:h2:mem:telemetry;DB_CLOSE_DELAY=-1;MODE=PostgreSQL"),
                Arguments.of("spring.flyway.user", "sa"),
                Arguments.of("spring.flyway.password", ""),
                Arguments.of("spring.flyway.locations", "classpath:db/migration"),
                Arguments.of("logging.structured.format.file", "ecs"),
                Arguments.of("logging.file.name", "logs/telemetry-ingestion-processing.log"),
                Arguments.of("logging.logback.rollingpolicy.max-file-size", "10MB"),
                Arguments.of("logging.logback.rollingpolicy.max-history", "14"),
                Arguments.of("logging.level.com.pulsestream.telemetry", "INFO"),
                Arguments.of("management.endpoints.web.exposure.include", "health,metrics"));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("literals")
    void yml_tabledPath_hasTabledLiteral(String path, String expected) {
        Object value = property(path);

        assertThat(value).as(path).isNotNull();
        assertThat(String.valueOf(value)).isEqualTo(expected);
    }

    @Test
    void yml_document_isSingleDocument() {
        assertThat(documents).hasSize(1);
    }

    @Test
    void yml_flywayLocation_startsWithClasspathPrefix() {
        assertThat(String.valueOf(property("spring.flyway.locations"))).startsWith("classpath:");
    }

    @Test
    void yml_document_isNestedWithNoDottedTopLevelKey() throws IOException {
        var resource = new ClassPathResource("application.yml");
        try (var in = resource.getInputStream()) {
            Map<?, ?> root = new org.yaml.snakeyaml.Yaml().load(in);
            assertThat(root.keySet()).noneMatch(k -> String.valueOf(k).contains("."));
        }
    }

    @Test
    void context_loads_withFlywayMigrationsApplied() {
        Long tables = db.sql("SELECT COUNT(*) AS c FROM telemetry_record")
                .map((row, md) -> row.get("c", Long.class)).one().block();

        assertThat(tables).isNotNull();
        assertThat(environment.getProperty("telemetry.reorder-window-seconds")).isEqualTo("60");
    }
}
