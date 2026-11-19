package com.pulsestream.telemetry.ingestion.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class DeviceCredentialAuthenticationManagerTest {

    private final PasswordEncoder encoder = new BCryptPasswordEncoder(4);

    private ReactiveUserDetailsService users() {
        return name -> "dev-1".equals(name)
                ? Mono.just(User.withUsername("dev-1").password(encoder.encode("s3cret"))
                        .authorities("SCOPE_telemetry:write").build())
                : Mono.empty();
    }

    private static Authentication credentials(String device, String secret) {
        return new UsernamePasswordAuthenticationToken(device, secret);
    }

    @Test
    void authenticate_validCredential_returnsAuthenticatedWithScopeAuthority() {
        var manager = new DeviceCredentialAuthenticationManager(users(), encoder);

        StepVerifier.create(manager.authenticate(credentials("dev-1", "s3cret")))
                .assertNext(a -> {
                    assertThat(a.isAuthenticated()).isTrue();
                    assertThat(a.getName()).isEqualTo("dev-1");
                    assertThat(a.getAuthorities()).extracting(GrantedAuthority::getAuthority)
                            .containsExactly("SCOPE_telemetry:write");
                })
                .verifyComplete();
    }

    @Test
    void authenticate_wrongSecret_completesEmpty() {
        var manager = new DeviceCredentialAuthenticationManager(users(), encoder);

        StepVerifier.create(manager.authenticate(credentials("dev-1", "wrong"))).verifyComplete();
    }

    @Test
    void authenticate_unknownDevice_completesEmpty() {
        var manager = new DeviceCredentialAuthenticationManager(users(), encoder);

        StepVerifier.create(manager.authenticate(credentials("ghost", "s3cret"))).verifyComplete();
    }

    @Test
    void authenticate_userServiceFails_completesEmptyWithoutError() {
        ReactiveUserDetailsService failing = name -> Mono.error(new IllegalStateException("db down"));
        var manager = new DeviceCredentialAuthenticationManager(failing, encoder);

        StepVerifier.create(manager.authenticate(credentials("dev-1", "s3cret"))).verifyComplete();
    }
}
