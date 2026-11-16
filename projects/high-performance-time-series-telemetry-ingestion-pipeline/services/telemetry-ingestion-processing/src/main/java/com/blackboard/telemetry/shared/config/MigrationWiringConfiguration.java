package com.blackboard.telemetry.shared.config;

import org.springframework.boot.autoconfigure.flyway.FlywayConfigurationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MigrationWiringConfiguration {

    // Packaged scripts keep the boot independent of the process working directory.
    @Bean
    public FlywayConfigurationCustomizer packagedMigrationLocations() {
        return configuration -> configuration.locations("classpath:db/migrations");
    }
}
