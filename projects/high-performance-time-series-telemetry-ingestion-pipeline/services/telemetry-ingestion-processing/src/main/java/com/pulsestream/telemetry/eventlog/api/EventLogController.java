package com.pulsestream.telemetry.eventlog.api;

import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.eventlog.application.EventLogService;

@RestController
public class EventLogController {

    private final EventLogService service;

    public EventLogController(EventLogService service) {
        this.service = service;
    }

    @GetMapping("/api/v1/telemetry/records")
    public Flux<TelemetrySample> records(@RequestParam String deviceId, @RequestParam long from, @RequestParam long to) {
        return service.query(deviceId, from, to);
    }
}
