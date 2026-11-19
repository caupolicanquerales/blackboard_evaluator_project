package com.pulsestream.telemetry.ingestion.infrastructure;

import java.util.Objects;
import org.springframework.security.authentication.ReactiveAuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.ReactiveUserDetailsService;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import reactor.core.publisher.Mono;

public class DeviceCredentialAuthenticationManager implements ReactiveAuthenticationManager {

    private final ReactiveUserDetailsService users;

    private final PasswordEncoder encoder;

    public DeviceCredentialAuthenticationManager(ReactiveUserDetailsService users, PasswordEncoder encoder) {
        this.users = Objects.requireNonNull(users, "users");
        this.encoder = Objects.requireNonNull(encoder, "encoder");
    }

    @Override
    public Mono<Authentication> authenticate(Authentication authentication) {
        Object principal = authentication.getPrincipal();
        Object credentials = authentication.getCredentials();
        if (principal == null || credentials == null) {
            return Mono.empty();
        }
        String rawSecret = credentials.toString();
        return users.findByUsername(principal.toString())
                .filter(DeviceCredentialAuthenticationManager::isUsable)
                .filter(user -> encoder.matches(rawSecret, user.getPassword()))
                .<Authentication>map(DeviceCredentialAuthenticationManager::toAuthenticated)
                .onErrorResume(error -> Mono.empty());
    }

    private static boolean isUsable(UserDetails user) {
        return user.isEnabled() && user.isAccountNonLocked() && user.isAccountNonExpired() && user.isCredentialsNonExpired();
    }

    private static Authentication toAuthenticated(UserDetails user) {
        return UsernamePasswordAuthenticationToken.authenticated(user.getUsername(), null, user.getAuthorities());
    }
}
