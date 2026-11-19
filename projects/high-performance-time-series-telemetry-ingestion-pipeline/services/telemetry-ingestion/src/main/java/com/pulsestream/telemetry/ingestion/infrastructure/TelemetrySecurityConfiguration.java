package com.pulsestream.telemetry.ingestion.infrastructure;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.function.BiFunction;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.security.web.authentication.preauth.x509.SubjectX500PrincipalExtractor;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.security.web.server.ServerAuthenticationEntryPoint;
import org.springframework.security.web.server.authentication.ReactivePreAuthenticatedAuthenticationManager;
import org.springframework.security.web.server.authorization.ServerAccessDeniedHandler;
import org.springframework.security.web.server.context.NoOpServerSecurityContextRepository;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;
import com.pulsestream.telemetry.ingestion.application.AuditEntry;
import com.pulsestream.telemetry.ingestion.application.AuditTrail;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.beans.factory.config.ConfigurableListableBeanFactory;
import com.pulsestream.telemetry.distribution.application.BroadcastService;
import com.pulsestream.telemetry.ingestion.application.IngestPacketUseCase;

@Configuration(proxyBeanMethods = false)
@EnableWebFluxSecurity
public class TelemetrySecurityConfiguration {

    @Bean
    public SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http, DeviceCredentialAuthenticationManager deviceManager, ReactiveUserDetailsService users, AuditTrail auditTrail, TelemetryMetrics metrics) {
        BiFunction<ServerWebExchange, HttpStatus, Mono<Void>> deny = (exchange, status) -> Mono.defer(() -> {
            String path = exchange.getRequest().getPath().value();
            if (path.startsWith("/telemetry/ingress")) {
                metrics.samplesIngested("refused");
            } else {
                metrics.broadcastDropped("unauthenticated");
            }
            String action = status == HttpStatus.UNAUTHORIZED ? "authentication-failure" : "authorization-denied";
            AuditEntry entry = new AuditEntry("anonymous", action, "DENIED", Instant.now(), path);
            byte[] payload = ("{\"code\":\"ACCESS_REFUSED\",\"message\":\"Access refused\",\"correlationId\":\"" + path + "\"}").getBytes(StandardCharsets.UTF_8);
            ServerHttpResponse response = exchange.getResponse();
            return auditTrail.record(entry).onErrorResume(error -> Mono.empty()).then(Mono.defer(() -> {
                response.setStatusCode(status);
                response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
                return response.writeWith(Mono.just(response.bufferFactory().wrap(payload)));
            }));
        });
        ServerAuthenticationEntryPoint entryPoint = (exchange, error) -> deny.apply(exchange, HttpStatus.UNAUTHORIZED);
        ServerAccessDeniedHandler deniedHandler = (exchange, error) -> deny.apply(exchange, HttpStatus.FORBIDDEN);
        return http.csrf(csrf -> csrf.disable()).securityContextRepository(NoOpServerSecurityContextRepository.getInstance()).httpBasic(basic -> basic.authenticationManager(deviceManager).authenticationEntryPoint(entryPoint)).x509(x509 -> x509.principalExtractor(new SubjectX500PrincipalExtractor()).authenticationManager(new ReactivePreAuthenticatedAuthenticationManager(users))).authorizeExchange(exchanges -> exchanges.pathMatchers(HttpMethod.POST, "/telemetry/ingress").hasAnyAuthority("SCOPE_telemetry:ingest", "SCOPE_telemetry:write").pathMatchers(HttpMethod.GET, "/telemetry/stream").hasAuthority("SCOPE_telemetry:subscribe").anyExchange().denyAll()).exceptionHandling(handling -> handling.authenticationEntryPoint(entryPoint).accessDeniedHandler(deniedHandler)).build();
    }

    @Bean
    public static BeanFactoryPostProcessor deferUnwiredControllers() {
        return factory -> {
            deferWhenMissing(factory, "windowBroadcastController", BroadcastService.class);
            deferWhenMissing(factory, "ingressPacketController", IngestPacketUseCase.class);
        };
    }

    private static void deferWhenMissing(ConfigurableListableBeanFactory factory, String controllerName, Class<?> dependency) {
        if (factory.containsBeanDefinition(controllerName) && factory.getBeanNamesForType(dependency, true, false).length == 0) {
            factory.getBeanDefinition(controllerName).setLazyInit(true);
        }
    }
}
