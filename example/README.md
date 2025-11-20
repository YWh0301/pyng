# PyNG Simulation for TIA Circuit Optimization

## Overview

This Python script performs automated circuit simulation and optimization for Transimpedance Amplifier (TIA) circuits using the PyNG interface to ngspice. The program systematically searches for optimal component values to achieve specific bandwidth targets while analyzing circuit performance metrics.

## Key Features

- **Automated Component Sweeping**: Systematically varies compensation inductance (Lc) and searches for optimal feedback resistance (Rf)
- **Bandwidth Targeting**: Uses bisection search to find Rf values that achieve 1MHz bandwidth
- **Multi-parameter Analysis**: Simultaneously evaluates gain, noise, stability, and frequency response
- **Model Flexibility**: Supports multiple feedback inductor models with different inductance values
- **Data Visualization**: Generates comprehensive plots showing performance trade-offs

## Circuit Configuration

The simulation is based on a TIA circuit with the following key components:
- **Feedback Inductor (Lf)**: Multiple models with inductance values from 10μH to 56μH
- **Feedback Capacitor (Cf)**: Automatically tuned to achieve 20MHz resonance peak
- **Compensation Inductor (Lc)**: Swept across a specified range (default: 1.25μH to 1.56μH)
- **Feedback Resistor (Rf)**: Dynamically adjusted to achieve target bandwidth

## Algorithm Description

### 1. Feedback Capacitor Optimization
- **Target**: Find Cf that positions gain peak at 20MHz
- **Method**: Bisection search with adaptive step sizing
- **Constraints**: Cf bounded between minimum (0.01pF) and maximum (100pF) values
- **Precision**: Target frequency accuracy of 0.2% (1/500)

### 2. Feedback Resistor Optimization
- **Target**: Find Rf that achieves 1MHz bandwidth
- **Method**: Hybrid search combining fixed-step and proportional bisection
- **Constraints**: Rf bounded between 1kΩ and 1000kΩ
- **Precision**: Bandwidth accuracy of 1% (1/100)

### 3. Performance Analysis
For each (Lf, Lc, Rf) combination, the script analyzes:
- **Gain Characteristics**: Peak value, bandwidth, -3dB frequencies
- **Noise Performance**: Output noise density at signal peak frequency
- **Stability**: Checks for oscillation via transient analysis
- **Data Validity**: Verifies bandwidth measurements aren't limited by simulation frequency range

## Usage

### Running Simulations
```bash
python change_Lc_Rf.py -s
```

### Generating Plots
```bash
python change_Lc_Rf.py -d data_file.pkl
```

### Command Line Arguments
- `-s, --sim`: Run the simulation function
- `-d, --draw <filename>`: Generate plots from saved data file

## Output Data

The simulation generates a pickle file containing:
- Lc sweep values
- Optimal Cf for each Lf model
- Rf values achieving 1MHz bandwidth
- Gain peak values and frequencies
- Bandwidth measurements
- Noise performance data
- Stability indicators
- Data validity flags

## Visualization

The plotting function creates three subplots:
1. **Gain vs Noise**: Shows trade-off between peak gain and output noise
2. **Frequency Analysis**: Displays gain peak frequency across Lc range
3. **Bandwidth vs Rf**: Illustrates the relationship between optimal Rf and achieved bandwidth

Color-coded regions indicate:
- **Red**: Circuit instability/oscillation
- **Light Blue**: Invalid bandwidth measurements
- **Violet**: Both instability and invalid data
- **Green**: Suboptimal Rf search results

## Dependencies

- numpy
- matplotlib
- pyng (ngspice interface)
- rich (progress bars)
- argparse

## Configuration Parameters

Key adjustable parameters in the script:
- `target_bandwidth`: 1MHz (bandwidth target)
- `target_peak_freq`: 20MHz (resonance target)
- `Lc_low`, `Lc_high`, `Lc_delta`: Compensation inductor sweep range
- `bandwidth_precision`, `peak_precision`: Search convergence criteria
- `sim_freq_low`, `sim_freq_high`: AC analysis frequency range

## Application Notes

This tool is particularly useful for:
- TIA design optimization for specific bandwidth requirements
- Understanding trade-offs between gain, noise, and stability
- Component selection for photodiode amplifiers and other current-to-voltage conversion applications
- Educational purposes for studying feedback amplifier design principles

The automated search approach significantly reduces manual iteration time while providing comprehensive performance characterization across the component design space.
