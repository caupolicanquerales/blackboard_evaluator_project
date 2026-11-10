package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.ProblemDetail;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.support.WebExchangeBindException;
import org.springframework.web.server.ServerWebInputException;

@ExtendWith(MockitoExtension.class)
class ApiExceptionHandlerTest {

    private final ApiExceptionHandler handler = new ApiExceptionHandler();

    @Mock
    private WebExchangeBindException bindException;

    @Test
    void handleBinding_fieldErrors_returns400() {
        when(bindException.getFieldErrors())
                .thenReturn(List.of(new FieldError("packet", "deviceId", "must not be blank")));

        ProblemDetail result = handler.handleBinding(bindException);

        assertThat(result.getStatus()).isEqualTo(400);
    }

    @Test
    void handleBadInput_malformedBody_returns400() {
        ProblemDetail result = handler.handleBadInput(new ServerWebInputException("bad body"));

        assertThat(result.getStatus()).isEqualTo(400);
    }

    @Test
    void handleIllegalArgument_anyMessage_returns400() {
        ProblemDetail result = handler.handleIllegalArgument(new IllegalArgumentException("invalid"));

        assertThat(result.getStatus()).isEqualTo(400);
    }

    @Test
    void handleOverflow_eventBusOverflow_returns503() {
        ProblemDetail result = handler.handleOverflow(new IllegalStateException("overflow"));

        assertThat(result.getStatus()).isEqualTo(503);
    }

    @Test
    void handleOverflow_anyException_bodyHasNoStackTrace() {
        ProblemDetail result = handler.handleOverflow(new IllegalStateException("overflow"));

        assertThat(String.valueOf(result.getDetail())).doesNotContain("at com.pulsestream");
    }
}
