package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.ConfigurationPropertySources;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.EnumerablePropertySource;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;

class ApplicationConfigTest {

    private static final String PROFILE_KEY = "spring.config.activate.on-profile";

    private Map<String, Object> base;
    private Map<String, Object> test;
    private String raw;

    @BeforeEach
    void load() throws IOException {
        var resource = new ClassPathResource("application.yml");
        raw = new String(resource.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        List<PropertySource<?>> docs = new YamlPropertySourceLoader().load("application", resource);
        base = new HashMap<>();
        test = new HashMap<>();
        for (PropertySource<?> doc : docs) {
            var source = (EnumerablePropertySource<?>) doc;
            var target = "test".equals(source.getProperty(PROFILE_KEY)) ? test : base;
            for (String name : source.getPropertyNames()) {
                target.put(name, source.getProperty(name));
            }
        }
    }

    @Test
    void load_producesBaseAndTestProfileDocuments() {
        assertThat(base).isNotEmpty();
        assertThat(test).isNotEmpty();
    }

    @Test
    void base_applicationName_isTelemetryIngestion() {
        assertThat(base.get("spring.application.name")).isEqualTo("telemetry-ingestion");
    }

    @Test
    void base_flywayLocations_pointToClasspathMigrations() {
        assertThat(base.get("spring.flyway.locations")).isEqualTo("classpath:db/migration");
    }

    @Test
    void base_jdbcAndR2dbcKeys_areDistinctAndPresent() {
        assertThat(base).containsKeys("spring.flyway.url", "spring.r2dbc.url");
        assertThat(base.get("spring.flyway.url")).isNotEqualTo(base.get("spring.r2dbc.url"));
    }

    @Test
    void base_telemetryKeys_areAllDeclared() {
        assertThat(base).containsKeys(
                "telemetry.reorder-window", "telemetry.reorder-buffer-capacity",
                "telemetry.window-duration", "telemetry.window-max-events",
                "telemetry.bus-capacity", "telemetry.broadcast-capacity",
                "telemetry.publisher-id", "telemetry.data-key");
    }

    @Test
    void base_errorKeys_hideInternals() {
        assertThat(base.get("server.error.include-stacktrace")).isEqualTo("never");
        assertThat(base.get("server.error.include-message")).isEqualTo("never");
    }

    @Test
    void base_dataKey_isEnvironmentPlaceholderNotLiteral() {
        assertThat(String.valueOf(base.get("telemetry.data-key"))).startsWith("${");
    }

    @Test
    void file_containsNoSecretLiteral() {
        assertThat(raw).doesNotContainIgnoringCase("password: ").doesNotContain("$2a$").doesNotContain("$2b$");
    }

    @Test
    void test_profile_usesH2WithFlywayEnabled() {
        assertThat(String.valueOf(test.get("spring.r2dbc.url"))).startsWith("r2dbc:h2:");
        assertThat(String.valueOf(test.get("spring.flyway.url"))).startsWith("jdbc:h2:");
        assertThat(String.valueOf(test.get("spring.flyway.enabled"))).isEqualTo("true");
    }

    @Test
    void base_telemetryPrefix_bindsToTelemetryProperties() {
        var sources = new MutablePropertySources();
        sources.addFirst(new MapPropertySource("base", base));
        var env = ConfigurationPropertySources.from(sources);

        var props = new Binder(env).bind("telemetry", TelemetryProperties.class);

        assertThat(props.isBound()).isTrue();
        assertThat(props.get().busCapacity()).isPositive();
    }
}
