package com.pulsestream.telemetry;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import com.pulsestream.telemetry.shared.config.TelemetryProperties;

@SpringBootApplication
@EnableConfigurationProperties(TelemetryProperties.class)
public class TelemetryIngestionApplication {

	public static void main(String[] args) {
		SpringApplication.run(TelemetryIngestionApplication.class, args);
	}

}
