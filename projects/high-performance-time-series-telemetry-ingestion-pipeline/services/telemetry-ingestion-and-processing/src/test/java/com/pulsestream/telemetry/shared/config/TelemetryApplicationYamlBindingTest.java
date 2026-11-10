package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.ConfigurationPropertySources;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;

class TelemetryApplicationYamlBindingTest {

    private static final String ROOT = "pulsestream.telemetry";

    private Binder binder;
    private PropertySource<?> source;

    @BeforeEach
    void loadYaml() throws IOException {
        List<PropertySource<?>> loaded = new YamlPropertySourceLoader()
                .load("application", new ClassPathResource("application.yml"));
        source = loaded.get(0);
        MutablePropertySources sources = new MutablePropertySources();
        sources.addFirst(source);
        binder = new Binder(ConfigurationPropertySources.from(sources));
    }

    private String string(String key) {
        return binder.bind(key, String.class).orElse(null);
    }

    private Integer integer(String key) {
        return binder.bind(key, Integer.class).orElse(null);
    }

    private Map<String, Object> boundary(String name) {
        Map<String, Map<String, Object>> all = binder
                .bind(ROOT + ".boundaries", Map.class).orElse(Map.of());
        Map<String, Object> entry = all.get(name);
        return entry != null ? entry : all.getOrDefault(name.replace('_', '-'), Map.of());
    }

    private void assertBoundary(String name, int min, Integer max) {
        Map<String, Object> b = boundary(name);
        assertThat(String.valueOf(b.get("min"))).isEqualTo(String.valueOf(min));
        if (max == null) {
            assertThat(b).doesNotContainKey("max");
        } else {
            assertThat(String.valueOf(b.get("max"))).isEqualTo(String.valueOf(max));
        }
    }

    @Test
    void yaml_applicationName_isDefined() {
        assertThat(string("spring.application.name")).isNotBlank();
    }

    @Test
    void yaml_r2dbc_readsConnectionFromEnvironmentVariables() {
        assertThat(string("spring.r2dbc.url")).contains("R2DBC_URL");
        assertThat(string("spring.r2dbc.username")).contains("DB_USER");
        assertThat(string("spring.r2dbc.password")).contains("DB_PASSWORD");
    }

    @Test
    void yaml_r2dbc_targetsLedgerSchema() {
        assertThat(String.valueOf(source.getProperty("spring.r2dbc.url"))).contains("ledger");
    }

    @Test
    void yaml_flyway_isEnabledWithEnvCredentialsAndLedgerSchema() {
        assertThat(binder.bind("spring.flyway.enabled", Boolean.class).orElse(false)).isTrue();
        assertThat(string("spring.flyway.url")).contains("jdbc:");
        assertThat(string("spring.flyway.user")).contains("DB_USER");
        assertThat(string("spring.flyway.password")).contains("DB_PASSWORD");
        assertThat(string("spring.flyway.locations")).isEqualTo("classpath:db/migration");
        assertThat(string("spring.flyway.schemas")).isEqualTo("ledger");
    }

    @Test
    void yaml_server_shutdownIsGraceful() {
        assertThat(string("server.shutdown")).isEqualTo("graceful");
    }

    @Test
    void yaml_telemetry_reorderWindowIsSixtySeconds() {
        assertThat(string(ROOT + ".reorder-window")).isEqualTo("PT60S");
        assertThat(integer(ROOT + ".reorder-buffer-capacity")).isPositive();
    }

    @Test
    void yaml_telemetry_windowSizeAndSlideAreDefined() {
        assertThat(string(ROOT + ".window.size")).isNotBlank();
        assertThat(string(ROOT + ".window.slide")).isNotBlank();
    }

    @Test
    void yaml_telemetry_everyChannelCapacityIsPositive() {
        Map<String, Object> channels = binder.bind(ROOT + ".channels", Map.class).orElse(Map.of());
        assertThat(channels).isNotEmpty();
        channels.values().forEach(v -> assertThat(Integer.valueOf(String.valueOf(v))).isPositive());
    }

    @Test
    void yaml_telemetry_boundariesMatchPhysiologicalLimits() {
        assertBoundary("heart_rate", 30, 240);
        assertBoundary("power", 0, 2500);
        assertBoundary("cadence", 0, 220);
        assertBoundary("swim_pace", 45, null);
    }
}
