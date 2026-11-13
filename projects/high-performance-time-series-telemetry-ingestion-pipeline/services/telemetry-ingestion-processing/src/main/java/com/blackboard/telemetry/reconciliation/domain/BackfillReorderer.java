package com.blackboard.telemetry.reconciliation.domain;

import java.util.List;
import java.util.Comparator;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;

public class BackfillReorderer {

    public List<TelemetrySample> reorder(List<TelemetrySample> samples) {
        return samples.stream().sorted(Comparator.comparing(TelemetrySample::tDevice)).toList();
    }
}
