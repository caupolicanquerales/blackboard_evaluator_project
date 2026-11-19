package com.pulsestream.telemetry.distribution.api;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import com.pulsestream.telemetry.distribution.application.BroadcastService;
import com.pulsestream.telemetry.distribution.domain.TelemetryWindowBroadcast;
import org.springframework.web.bind.annotation.RequestMapping;

@RestController
public class WindowBroadcastController {

    private final BroadcastService service;

    public WindowBroadcastController(BroadcastService service) {
        this.service = service;
    }

    @GetMapping(value = "/telemetry/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<TelemetryWindowBroadcast> stream() {
        return service.subscribe();
    }
}
