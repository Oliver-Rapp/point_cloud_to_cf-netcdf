# Round-trip test report

**Date:** 2026-03-12T15:07:52Z  
**Branch:** integration/round-trip-test  

---

## Test data

| File | Points | Format |
|---|---|---|
| `DJI_sample_100k.las` | 100,000 | LAS 1.4, DJI Zenmuse L1, UTM 33N, has RGB + GPS time |
| `VNIR_sample_100k.ply` | 100,000 | PLY binary_little_endian, HySpex VNIR 1800, UTM 33N, has normals/view vectors/pixel coords/epoch |

---

## Results summary

| Test | Description | Conversion | Status |
|---|---|---|---|
| T1 | LAS → NC (CRS from VLRs) | forward | ✅ PASS |
| T2 | LAS → NC (CRS from YAML) | forward | ✅ PASS |
| T3 | LAS → NC (CRS from proj4) | forward | ✅ PASS |
| T4 | PLY → NC (CRS from header comment) | forward | ✅ PASS |
| T5 | PLY → NC (CRS from YAML) | forward | ✅ PASS |
| T6 | NC → LAS round-trip (T1 source) | reverse | ✅ PASS |
| T7 | NC → PLY cross-format (LAS → PLY) | reverse | ✅ PASS |
| T8 | NC → PLY round-trip (T4 source) | reverse | ✅ PASS |
| T9 | NC → LAS cross-format (PLY → LAS) | reverse | ✅ PASS |
| CRS_CONSISTENCY | CRS method consistency (T1 vs T2 vs T3) | check | ✅ PASS |

---

## Detailed checks

### T1: LAS → NC (CRS from VLRs)

| Check | Result | Detail |
|---|---|---|
| NetCDF exists | ✅ |  |
| var:X present | ✅ |  |
| var:Y present | ✅ |  |
| var:Z present | ✅ |  |
| var:latitude present | ✅ |  |
| var:longitude present | ✅ |  |
| var:altitude present | ✅ |  |
| var:red present | ✅ |  |
| var:green present | ✅ |  |
| var:blue present | ✅ |  |
| var:epoch_time present | ✅ |  |
| var:scan_angle_rank present | ✅ |  |
| crs variable present | ✅ |  |
| crs:grid_mapping_name set | ✅ | transverse_mercator |
| lat range valid | ✅ | min=78.6510 max=78.6521 expected [76.0,82.0] |
| lon range valid | ✅ | min=17.7773 max=17.7856 expected [13.0,22.0] |
| attr:title | ✅ |  |
| attr:Conventions | ✅ |  |
| attr:featureType | ✅ |  |
| attr:geospatial_lat_min | ✅ |  |
| Conventions=CF-1.8,ACDD-1.3 | ✅ | CF-1.8, ACDD-1.3 |

### T2: LAS → NC (CRS from YAML)

| Check | Result | Detail |
|---|---|---|
| NetCDF exists | ✅ |  |
| var:X present | ✅ |  |
| var:Y present | ✅ |  |
| var:Z present | ✅ |  |
| var:latitude present | ✅ |  |
| var:longitude present | ✅ |  |
| var:altitude present | ✅ |  |
| var:red present | ✅ |  |
| var:green present | ✅ |  |
| var:blue present | ✅ |  |
| var:epoch_time present | ✅ |  |
| var:scan_angle_rank present | ✅ |  |
| crs variable present | ✅ |  |
| crs:grid_mapping_name set | ✅ | transverse_mercator |
| lat range valid | ✅ | min=78.6510 max=78.6521 expected [76.0,82.0] |
| lon range valid | ✅ | min=17.7773 max=17.7856 expected [13.0,22.0] |
| attr:title | ✅ |  |
| attr:Conventions | ✅ |  |
| attr:featureType | ✅ |  |
| attr:geospatial_lat_min | ✅ |  |
| Conventions=CF-1.8,ACDD-1.3 | ✅ | CF-1.8, ACDD-1.3 |

### T3: LAS → NC (CRS from proj4)

| Check | Result | Detail |
|---|---|---|
| NetCDF exists | ✅ |  |
| var:X present | ✅ |  |
| var:Y present | ✅ |  |
| var:Z present | ✅ |  |
| var:latitude present | ✅ |  |
| var:longitude present | ✅ |  |
| var:altitude present | ✅ |  |
| var:red present | ✅ |  |
| var:green present | ✅ |  |
| var:blue present | ✅ |  |
| var:epoch_time present | ✅ |  |
| var:scan_angle_rank present | ✅ |  |
| crs variable present | ✅ |  |
| crs:grid_mapping_name set | ✅ | transverse_mercator |
| lat range valid | ✅ | min=78.6510 max=78.6521 expected [76.0,82.0] |
| lon range valid | ✅ | min=17.7773 max=17.7856 expected [13.0,22.0] |
| attr:title | ✅ |  |
| attr:Conventions | ✅ |  |
| attr:featureType | ✅ |  |
| attr:geospatial_lat_min | ✅ |  |
| Conventions=CF-1.8,ACDD-1.3 | ✅ | CF-1.8, ACDD-1.3 |

### T4: PLY → NC (CRS from header comment)

| Check | Result | Detail |
|---|---|---|
| NetCDF exists | ✅ |  |
| var:X present | ✅ |  |
| var:Y present | ✅ |  |
| var:Z present | ✅ |  |
| var:latitude present | ✅ |  |
| var:longitude present | ✅ |  |
| var:red present | ✅ |  |
| var:green present | ✅ |  |
| var:blue present | ✅ |  |
| var:nx present | ✅ |  |
| var:ny present | ✅ |  |
| var:nz present | ✅ |  |
| var:vx present | ✅ |  |
| var:vy present | ✅ |  |
| var:vz present | ✅ |  |
| var:px present | ✅ |  |
| var:py present | ✅ |  |
| crs variable present | ✅ |  |
| crs:grid_mapping_name set | ✅ | transverse_mercator |
| lat range valid | ✅ | min=78.2421 max=78.2464 expected [76.0,82.0] |
| lon range valid | ✅ | min=15.4862 max=15.4947 expected [13.0,22.0] |
| attr:title | ✅ |  |
| attr:Conventions | ✅ |  |
| attr:featureType | ✅ |  |
| attr:geospatial_lat_min | ✅ |  |
| Conventions=CF-1.8,ACDD-1.3 | ✅ | CF-1.8, ACDD-1.3 |

### T5: PLY → NC (CRS from YAML)

| Check | Result | Detail |
|---|---|---|
| NetCDF exists | ✅ |  |
| var:X present | ✅ |  |
| var:Y present | ✅ |  |
| var:Z present | ✅ |  |
| var:latitude present | ✅ |  |
| var:longitude present | ✅ |  |
| var:red present | ✅ |  |
| var:green present | ✅ |  |
| var:blue present | ✅ |  |
| var:nx present | ✅ |  |
| var:ny present | ✅ |  |
| var:nz present | ✅ |  |
| var:vx present | ✅ |  |
| var:vy present | ✅ |  |
| var:vz present | ✅ |  |
| var:px present | ✅ |  |
| var:py present | ✅ |  |
| crs variable present | ✅ |  |
| crs:grid_mapping_name set | ✅ | transverse_mercator |
| lat range valid | ✅ | min=78.2421 max=78.2464 expected [76.0,82.0] |
| lon range valid | ✅ | min=15.4862 max=15.4947 expected [13.0,22.0] |
| attr:title | ✅ |  |
| attr:Conventions | ✅ |  |
| attr:featureType | ✅ |  |
| attr:geospatial_lat_min | ✅ |  |
| Conventions=CF-1.8,ACDD-1.3 | ✅ | CF-1.8, ACDD-1.3 |

### T6: NC → LAS round-trip (T1 source)

| Check | Result | Detail |
|---|---|---|
| output exists | ✅ |  |
| point count | ✅ | 100000 (expected 100000) |
| x accuracy | ✅ | max_err=0.000500 m (orig_scale=0.0001 m, rt_scale=0.001 m) |
| y accuracy | ✅ | max_err=0.000500 m (orig_scale=0.0001 m, rt_scale=0.001 m) |
| z accuracy | ✅ | max_err=0.000517 m (orig_scale=0.0001 m, rt_scale=0.001 m) |
| red round-trip | ✅ | max_diff=0 |
| green round-trip | ✅ | max_diff=0 |
| blue round-trip | ✅ | max_diff=0 |
| gps_time round-trip | ✅ | max_err=0.000000 s |
| scan_angle round-trip | ✅ | max_err=0.0040 deg |
| CRS in output LAS | ✅ | 32633 |

### T7: NC → PLY cross-format (LAS → PLY)

| Check | Result | Detail |
|---|---|---|
| output exists | ✅ |  |
| point count | ✅ | 100000 (expected 100000) |
| x accuracy (LAS→PLY) | ✅ | max_err=0.000000 m (tol=0.01 m) |
| y accuracy (LAS→PLY) | ✅ | max_err=0.000000 m (tol=0.01 m) |
| z accuracy (LAS→PLY) | ✅ | max_err=0.000031 m (tol=0.01 m) |
| utm_crs comment in PLY | ✅ | processing_time_epoch=1773328070.291628; utm_crs=PRO... |

### T8: NC → PLY round-trip (T4 source)

| Check | Result | Detail |
|---|---|---|
| output exists | ✅ |  |
| point count | ✅ | 100000 (expected 100000) |
| x accuracy | ✅ | max_err=0.00000000 m (tol=0.01 m) |
| y accuracy | ✅ | max_err=0.00000000 m (tol=0.01 m) |
| z accuracy | ✅ | max_err=0.00000191 m (tol=0.01 m) |
| red round-trip | ✅ | max_diff=0 |
| green round-trip | ✅ | max_diff=0 |
| blue round-trip | ✅ | max_diff=0 |
| nx accuracy | ✅ | max_err=0.00e+00 |
| ny accuracy | ✅ | max_err=0.00e+00 |
| nz accuracy | ✅ | max_err=0.00e+00 |
| normal vectors unit length | ✅ | mean_len=1.0000 max_dev=0.0000 |
| vx accuracy | ✅ | max_err=0.00e+00 |
| vy accuracy | ✅ | max_err=0.00e+00 |
| vz accuracy | ✅ | max_err=0.00e+00 |
| px round-trip | ✅ | max_diff=0 |
| py round-trip | ✅ | max_diff=0 |
| epoch time round-trip | ✅ | max_err=0.000000 s |
| utm_crs comment in PLY | ✅ | processing_time_epoch=1773328071.140297; utm_crs=PRO... |

### T9: NC → LAS cross-format (PLY → LAS)

| Check | Result | Detail |
|---|---|---|
| output exists | ✅ |  |
| point count | ✅ | 100000 (expected 100000) |
| x accuracy (PLY→LAS) | ✅ | max_err=0.000500 m (tol=0.01 m) |
| y accuracy (PLY→LAS) | ✅ | max_err=0.000500 m (tol=0.01 m) |
| z accuracy (PLY→LAS) | ✅ | max_err=0.000502 m (tol=0.01 m) |
| CRS in output LAS | ✅ | 32633 |

### CRS_CONSISTENCY: CRS method consistency (T1 vs T2 vs T3)

| Check | Result | Detail |
|---|---|---|
| lat: T1_VLR vs T2_YAML | ✅ | max_diff=0.00e+00 deg |
| lat: T1_VLR vs T3_proj4 | ✅ | max_diff=0.00e+00 deg |
| lat: T2_YAML vs T3_proj4 | ✅ | max_diff=0.00e+00 deg |

---

## Known limitations

| Limitation | Impact |
|---|---|
| Only UTM zone 33N data | Cannot test CRS reprojection for other zones/datums |
| Only 2 sensor types (DJI L1 + HySpex VNIR) | No variety in LAS point formats or GPS time encoding |
| No GPS Week Time file | Cannot test GPS Week Time rejection error |
| No PLY with pre-existing lat/lon columns | Cannot test that code path (known NameError bug) |
| HySpex hyperspectral intensity | 2D intensity not recoverable by design; tested that other variables are unaffected |
| No bad/malformed inputs | No negative testing |
| GPS time leap seconds | Configurable via gps_leap_seconds in to_pc_config.yaml; must be updated manually if a new leap second is added |

