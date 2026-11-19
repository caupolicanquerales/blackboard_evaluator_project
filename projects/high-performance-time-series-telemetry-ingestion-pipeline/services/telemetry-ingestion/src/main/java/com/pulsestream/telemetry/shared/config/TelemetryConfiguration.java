package com.pulsestream.telemetry.shared.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.core.userdetails.MapReactiveUserDetailsService;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.r2dbc.core.DatabaseClient;
import io.micrometer.core.instrument.MeterRegistry;
import java.security.SecureRandom;
import java.time.Clock;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import com.pulsestream.telemetry.ingestion.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.ingestion.application.BackfillReorderer;
import com.pulsestream.telemetry.ingestion.application.IngestPacketUseCase;
import com.pulsestream.telemetry.ingestion.infrastructure.Sha256RedactionAdapter;
import com.pulsestream.telemetry.ingestion.infrastructure.AesGcmPayloadCipher;
import com.pulsestream.telemetry.ingestion.infrastructure.R2dbcTelemetryRecordRepository;
import com.pulsestream.telemetry.ingestion.infrastructure.R2dbcAuditTrail;
import com.pulsestream.telemetry.ingestion.infrastructure.DeviceCredentialAuthenticationManager;
import com.pulsestream.telemetry.distribution.infrastructure.InProcessEventBus;
import com.pulsestream.telemetry.distribution.infrastructure.BroadcastLifecycle;
import com.pulsestream.telemetry.distribution.application.TrustedPublisherPolicy;
import com.pulsestream.telemetry.distribution.application.BroadcastService;
import com.pulsestream.telemetry.distribution.api.ValidatedEventConsumer;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;

@Configuration(proxyBeanMethods = false)
public class TelemetryConfiguration {

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return PasswordEncoderFactories.createDelegatingPasswordEncoder();
    }

    @Bean
    public MapReactiveUserDetailsService userDetailsService(TelemetryProperties props, PasswordEncoder encoder) {
        List<UserDetails> users = new ArrayList<>();
        for (TelemetryProperties.Credential c : props.devices()) {
            users.add(User.withUsername(c.id()).password(c.secretHash()).authorities("SCOPE_" + c.scope()).build());
        }
        for (TelemetryProperties.Credential c : props.consumers()) {
            users.add(User.withUsername(c.id()).password(c.secretHash()).authorities("SCOPE_" + c.scope()).build());
        }
        return new MapReactiveUserDetailsService(users);
    }

    @Bean
    public TelemetryMetrics telemetryMetrics(MeterRegistry registry) {
        return new TelemetryMetrics(registry);
    }

    @Bean
    @ConditionalOnMissingBean
    public SensorMetricBoundary sensorMetricBoundary() {
        return new SensorMetricBoundary();
    }

    @Bean
    @ConditionalOnMissingBean
    public BackfillReorderer backfillReorderer(TelemetryProperties props, TelemetryMetrics metrics) {
        return new BackfillReorderer(props.reorderWindow(), props.reorderBufferCapacity(), metrics);
    }

    @Bean
    @ConditionalOnMissingBean
    public Sha256RedactionAdapter sha256RedactionAdapter() {
        return new Sha256RedactionAdapter();
    }

    @Bean
    public AesGcmPayloadCipher aesGcmPayloadCipher(TelemetryProperties props, Environment env) {
        String dataKey = props.dataKey();
        if (dataKey == null || dataKey.isBlank()) {
            if (!env.acceptsProfiles(Profiles.of("test"))) {
                throw new IllegalStateException("telemetry.data-key must be configured");
            }
            byte[] key = new byte[32];
            new SecureRandom().nextBytes(key);
            return new AesGcmPayloadCipher(key);
        }
        return new AesGcmPayloadCipher(Base64.getDecoder().decode(dataKey));
    }

    @Bean
    @ConditionalOnMissingBean
    public R2dbcTelemetryRecordRepository r2dbcTelemetryRecordRepository(DatabaseClient client, AesGcmPayloadCipher cipher) {
        return new R2dbcTelemetryRecordRepository(client, cipher);
    }

    @Bean
    @ConditionalOnMissingBean
    public R2dbcAuditTrail r2dbcAuditTrail(DatabaseClient client) {
        return new R2dbcAuditTrail(client);
    }

    @Bean
    public InProcessEventBus eventBus(TelemetryProperties props, TelemetryMetrics metrics) {
        return new InProcessEventBus(props.busCapacity(), metrics);
    }

    @Bean
    public TrustedPublisherPolicy trustedPublisherPolicy(TelemetryProperties props) {
        return new TrustedPublisherPolicy(props.publisherId());
    }

    @Bean
    @ConditionalOnMissingBean
    public ValidatedEventConsumer validatedEventConsumer(TrustedPublisherPolicy policy, R2dbcAuditTrail audit, Sha256RedactionAdapter redaction, TelemetryMetrics metrics, TelemetryProperties props) {
        return new ValidatedEventConsumer(policy, audit, redaction, metrics, props.windowDuration(), props.windowMaxEvents());
    }

    @Bean
    public DeviceCredentialAuthenticationManager deviceCredentialAuthenticationManager(MapReactiveUserDetailsService users, PasswordEncoder encoder) {
        return new DeviceCredentialAuthenticationManager(users, encoder);
    }

    @Bean
    public IngestPacketUseCase ingestPacketUseCase(R2dbcTelemetryRecordRepository repository, InProcessEventBus bus, R2dbcAuditTrail audit, SensorMetricBoundary boundary, BackfillReorderer reorderer, Sha256RedactionAdapter redaction, TelemetryMetrics metrics, Clock clock, TelemetryProperties props) {
        return new IngestPacketUseCase(repository, bus, audit, boundary, reorderer, redaction, metrics, clock, props.reorderWindow(), props.publisherId());
    }

    @Bean
    public BroadcastService broadcastService(ValidatedEventConsumer buffer, InProcessEventBus bus, TelemetryMetrics metrics, TelemetryProperties props) {
        return new BroadcastService(buffer, bus, metrics, props.broadcastCapacity());
    }

    @Bean
    public BroadcastLifecycle broadcastLifecycle(BroadcastService service) {
        return new BroadcastLifecycle(service);
    }
}
