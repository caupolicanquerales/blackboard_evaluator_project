package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mockingDetails;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.reactive.server.SecurityMockServerConfigurers.mockUser;
import static org.springframework.web.reactive.function.server.RequestPredicates.GET;
import static org.springframework.web.reactive.function.server.RequestPredicates.POST;
import static org.springframework.web.reactive.function.server.RouterFunctions.route;

import com.pulsestream.telemetry.ingestion.application.AuditTrail;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@WebFluxTest
@Import({TelemetrySecurityConfiguration.class, TelemetrySecurityConfigurationTest.Routes.class})
class TelemetrySecurityConfigurationTest {

    @TestConfiguration
    static class Routes {
        @Bean
        RouterFunction<ServerResponse> testRoutes() {
            return route(POST("/telemetry/ingress"), r -> ServerResponse.accepted().build())
                    .andRoute(GET("/telemetry/stream"), r -> ServerResponse.ok().build())
                    .andRoute(GET("/unknown/path"), r -> ServerResponse.ok().build());
        }
    }

    @Autowired
    WebTestClient client;

    @MockitoBean
    DeviceCredentialAuthenticationManager deviceManager;
    @MockitoBean
    ReactiveUserDetailsService users;
    @MockitoBean
    AuditTrail auditTrail;
    @MockitoBean
    TelemetryMetrics metrics;

    @BeforeEach
    void stubAudit() {
        when(auditTrail.record(any())).thenReturn(Mono.empty());
    }

    private WebTestClient withScope(String scope) {
        return client.mutateWith(mockUser("dev-1").authorities(new SimpleGrantedAuthority("SCOPE_" + scope)));
    }

    @Test
    void ingress_withWriteScope_isPermitted() {
        withScope("telemetry:write").post().uri("/telemetry/ingress").exchange().expectStatus().isAccepted();
    }

    @Test
    void ingress_withoutCredential_returns401() {
        client.post().uri("/telemetry/ingress").exchange().expectStatus().isUnauthorized();
    }

    @Test
    void stream_withSubscribeScope_isPermitted() {
        withScope("telemetry:subscribe").get().uri("/telemetry/stream").exchange().expectStatus().isOk();
    }

    @Test
    void stream_withoutScope_isRefused() {
        withScope("other:scope").get().uri("/telemetry/stream").exchange().expectStatus().is4xxClientError();
    }

    @Test
    void stream_withoutCredentialAndWithoutScope_areRefusedWithSameBody() {
        byte[] anonymous = client.get().uri("/telemetry/stream").exchange().expectStatus().is4xxClientError()
                .expectBody().returnResult().getResponseBodyContent();
        byte[] scopeless = withScope("other:scope").get().uri("/telemetry/stream").exchange()
                .expectStatus().is4xxClientError().expectBody().returnResult().getResponseBodyContent();

        assertThat(scopeless == null ? new byte[0] : scopeless)
                .isEqualTo(anonymous == null ? new byte[0] : anonymous);
    }

    @Test
    void unknownPath_isDenied() {
        withScope("telemetry:write").get().uri("/unknown/path").exchange().expectStatus().is4xxClientError();
    }

    @Test
    void denial_writesAuditAndIncrementsMeter() {
        client.post().uri("/telemetry/ingress").exchange().expectStatus().isUnauthorized();

        verify(auditTrail).record(any());
        assertThat(mockingDetails(metrics).getInvocations()).isNotEmpty();
    }

    @Test
    void denial_body_hasOnlyCodeMessageAndCorrelationKey() {
        client.post().uri("/telemetry/ingress").exchange().expectStatus().isUnauthorized()
                .expectBody(Map.class).value(body -> {
                    assertThat(body).hasSize(3);
                    assertThat(body.keySet()).contains("code", "message");
                });
    }
}
