

-- DidaShopping 周度酒店促销清单 + MECE分流 + 五组实验分组
--
-- 输出粒度：一行一个 standard_hotel_id。
-- 默认输出近30天请求PV>=10的完整MECE分类；experiment_eligible=1 为最终促销清单。
-- 分组：同一候选母池分为2个对照组和3个实验组，完整相似五联组内每组各1家；
--       各分层不足5家的尾部酒店统一按固定seed再分配，使五组数量相差不超过1家。
--
-- 重要：
-- 1. 日期自动截止到 dwd_hotel_shopping_funnel_detail_d_f 的最新完整 metric_date。
-- 2. 历史有价来自Shopping真实请求漏斗；未来可售来自 supplier_hotel_day_count_dws。
-- 3. Shopping与全Dida订单分开聚合；全Dida利润只作为Shopping无产酒店的保守参考。
-- 4. SQL分组是可复现的“分层 + 相似排序 + 五联组随机”；若用于正式大额实验，
--    仍建议导出后复核五组SMD，并在同一五联组内做二次交换优化。

WITH params AS (
    SELECT
        MAX(metric_date::date)::date AS metric_end_date,
        (MAX(metric_date::date)::date - INTERVAL '29 days')::date AS metric_start_30,
        (MAX(metric_date::date)::date - INTERVAL '89 days')::date AS metric_start_90,
        (MAX(metric_date::date)::date - INTERVAL '13 days')::date AS start_prev_7,
        (MAX(metric_date::date)::date - INTERVAL '7 days')::date AS end_prev_7,
        (MAX(metric_date::date)::date - INTERVAL '6 days')::date AS start_recent_7,
        'weekly_promo_20260828_v1'::text AS assignment_seed
    FROM dwd.dwd_hotel_shopping_funnel_detail_d_f
),
latest_supply AS (
    SELECT MAX(date)::date AS supply_snapshot_date
    FROM bizanalysis.supplier_hotel_day_count_dws
),

-- 1. Shopping真实请求漏斗：宽表的available步骤应已在request粒度完成“有价优先”聚合。
funnel_30 AS (
    SELECT
        f.standard_hotel_id::text AS standard_hotel_id,
        MAX(f.dida_hotel_name) AS hotel_name,
        MAX(f.country_code) AS country_code,
        MAX(f.country_name) AS country_name,
        MAX(f.city_name) AS destination_name,
        COUNT(DISTINCT CASE WHEN f.step_code = 'request' THEN f.pv_key END) AS request_pv_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'available' THEN f.pv_key END) AS available_pv_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'expose' THEN f.rp_pv_key END) AS expose_rp_pv_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'click' THEN f.rp_pv_key END) AS click_rp_pv_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'prebook' THEN f.rp_pv_key END) AS prebook_rp_pv_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'click_payment' THEN f.rp_pv_key END) AS payment_rp_pv_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'request' THEN f.user_id END) AS request_user_cnt_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'request' THEN f.client_id END) AS request_client_cnt_30,
        COUNT(DISTINCT CASE WHEN f.step_code = 'request' THEN f.metric_date::date END) AS request_day_cnt_30,
        COUNT(DISTINCT CASE
            WHEN f.metric_date::date BETWEEN p.start_prev_7 AND p.end_prev_7
             AND f.step_code = 'request' THEN f.pv_key END) AS request_pv_prev7,
        COUNT(DISTINCT CASE
            WHEN f.metric_date::date BETWEEN p.start_recent_7 AND p.metric_end_date
             AND f.step_code = 'request' THEN f.pv_key END) AS request_pv_recent7,
        COUNT(DISTINCT CASE
            WHEN f.metric_date::date BETWEEN p.start_prev_7 AND p.end_prev_7
             AND f.step_code = 'available' THEN f.pv_key END) AS available_pv_prev7,
        COUNT(DISTINCT CASE
            WHEN f.metric_date::date BETWEEN p.start_recent_7 AND p.metric_end_date
             AND f.step_code = 'available' THEN f.pv_key END) AS available_pv_recent7
    FROM dwd.dwd_hotel_shopping_funnel_detail_d_f f
    CROSS JOIN params p
    WHERE f.metric_date::date BETWEEN p.metric_start_30 AND p.metric_end_date
      AND f.standard_hotel_id ~ '^[0-9]+$'
    GROUP BY f.standard_hotel_id
),
funnel_area AS (
    SELECT
        f.*,
        SUM(f.request_pv_prev7) OVER (PARTITION BY f.country_code) AS country_request_pv_prev7,
        SUM(f.request_pv_recent7) OVER (PARTITION BY f.country_code) AS country_request_pv_recent7,
        SUM(f.request_pv_prev7) OVER (
            PARTITION BY f.country_code, f.destination_name
        ) AS destination_request_pv_prev7,
        SUM(f.request_pv_recent7) OVER (
            PARTITION BY f.country_code, f.destination_name
        ) AS destination_request_pv_recent7
    FROM funnel_30 f
),
demand_threshold AS (
    SELECT
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY request_pv_30) AS request_pv_p90
    FROM funnel_30
    WHERE request_pv_30 > 0
),

-- 2. Shopping有效订单：先压到booking唯一粒度，避免订单事实表重复行放大TTV/GP。
shopping_order_raw AS (
    SELECT
        b.channel_booking_number::text AS channel_booking_number,
        b.dida_hotel_id::text AS standard_hotel_id,
        b.shopping_userid::text AS user_id,
        b.client_id::text AS client_id,
        b.supplier_id::text AS supplier_id,
        b.channel_create_time::date AS booking_date,
        COALESCE(b.channel_room_night, 0) AS rns,
        COALESCE(b.channel_price_cny, 0) AS ttv_cny,
        COALESCE(b.channel_combined_revenue_cny, 0) AS gp_cny
    FROM dwd.dwd_dida_channel_supplier_booking_base_d b
    CROSS JOIN params p
    WHERE b.channel_desc = 'DidaShopping'
      AND b.rebook_sequence = 1
      AND b.dida_hotel_id IS NOT NULL
      AND b.channel_create_time >= p.metric_start_30::timestamp
      AND b.channel_create_time < (p.metric_end_date + INTERVAL '1 day')::timestamp
      AND b.channel_status_code IN (2, 3)
      AND b.supplier_status_code IN (2, 3)
      AND (
          b.channel_booking_cancel_time IS NULL
          OR TO_CHAR(b.channel_create_time, 'YYYY-MM-DD')
             <> TO_CHAR(b.channel_booking_cancel_time, 'YYYY-MM-DD')
      )
),
shopping_order_base AS (
    SELECT
        channel_booking_number,
        MAX(standard_hotel_id) AS standard_hotel_id,
        MAX(user_id) AS user_id,
        MAX(client_id) AS client_id,
        MAX(supplier_id) AS supplier_id,
        MIN(booking_date) AS booking_date,
        MAX(rns) AS rns,
        MAX(ttv_cny) AS ttv_cny,
        MAX(gp_cny) AS gp_cny
    FROM shopping_order_raw
    GROUP BY channel_booking_number
),
shopping_order_agg AS (
    SELECT
        standard_hotel_id,
        COUNT(*) AS valid_bks_30,
        COUNT(DISTINCT user_id) AS valid_user_cnt_30,
        COUNT(DISTINCT client_id) AS valid_client_cnt_30,
        COUNT(DISTINCT supplier_id) AS valid_supplier_cnt_30,
        COUNT(DISTINCT booking_date) AS valid_booking_days_30,
        SUM(rns) AS valid_rns_30,
        SUM(ttv_cny) AS valid_ttv_cny_30,
        SUM(gp_cny) AS valid_gp_cny_30,
        SUM(CASE WHEN ttv_cny > 0 AND gp_cny / ttv_cny >= 0.10 THEN 1 ELSE 0 END) AS gpr_ge10_bks_30,
        SUM(CASE WHEN gp_cny < 0 THEN 1 ELSE 0 END) AS negative_gp_bks_30
    FROM shopping_order_base
    GROUP BY standard_hotel_id
),
shopping_daily_gpr AS (
    SELECT
        standard_hotel_id,
        booking_date,
        SUM(gp_cny) / NULLIF(SUM(ttv_cny), 0) AS daily_gpr
    FROM shopping_order_base
    GROUP BY standard_hotel_id, booking_date
),
shopping_daily_agg AS (
    SELECT
        standard_hotel_id,
        COUNT(*) AS gpr_valid_days_30,
        SUM(CASE WHEN daily_gpr >= 0.10 THEN 1 ELSE 0 END) AS gpr_ge10_days_30,
        SUM(CASE WHEN daily_gpr < 0 THEN 1 ELSE 0 END) AS negative_gpr_days_30,
        MIN(daily_gpr) AS min_daily_gpr_30
    FROM shopping_daily_gpr
    WHERE daily_gpr IS NOT NULL
    GROUP BY standard_hotel_id
),

-- 3. 全Dida有效订单：仅给Shopping无产酒店提供50%单均GP的保守参考。
all_platform_order_raw AS (
    SELECT
        b.channel_booking_number::text AS channel_booking_number,
        b.dida_hotel_id::text AS standard_hotel_id,
        COALESCE(b.channel_price_cny, 0) AS ttv_cny,
        COALESCE(b.channel_combined_revenue_cny, 0) AS gp_cny
    FROM dwd.dwd_dida_channel_supplier_booking_base_d b
    CROSS JOIN params p
    WHERE b.rebook_sequence = 1
      AND b.dida_hotel_id IS NOT NULL
      AND b.channel_create_time >= p.metric_start_30::timestamp
      AND b.channel_create_time < (p.metric_end_date + INTERVAL '1 day')::timestamp
      AND b.channel_status_code IN (2, 3)
      AND b.supplier_status_code IN (2, 3)
      AND (
          b.channel_booking_cancel_time IS NULL
          OR TO_CHAR(b.channel_create_time, 'YYYY-MM-DD')
             <> TO_CHAR(b.channel_booking_cancel_time, 'YYYY-MM-DD')
      )
),
all_platform_order_base AS (
    SELECT
        channel_booking_number,
        MAX(standard_hotel_id) AS standard_hotel_id,
        MAX(ttv_cny) AS ttv_cny,
        MAX(gp_cny) AS gp_cny
    FROM all_platform_order_raw
    GROUP BY channel_booking_number
),
all_platform_order_agg AS (
    SELECT
        standard_hotel_id,
        COUNT(*) AS all_platform_valid_bks_30,
        SUM(ttv_cny) AS all_platform_valid_ttv_cny_30,
        SUM(gp_cny) AS all_platform_valid_gp_cny_30
    FROM all_platform_order_base
    GROUP BY standard_hotel_id
),

-- 4. 未来30天Top可售供应商。
future_supplier_rank AS (
    SELECT
        s.dida_hotel_id::text AS standard_hotel_id,
        s.supplier_id,
        MAX(s.has_rate_days) AS has_rate_days_30,
        ROW_NUMBER() OVER (
            PARTITION BY s.dida_hotel_id
            ORDER BY MAX(s.has_rate_days) DESC, s.supplier_id
        ) AS rn
    FROM bizanalysis.supplier_hotel_day_count_dws s
    CROSS JOIN latest_supply l
    WHERE s.date = l.supply_snapshot_date
      AND s.has_rate_days > 0
    GROUP BY s.dida_hotel_id, s.supplier_id
),
future_supplier AS (
    SELECT
        f.standard_hotel_id,
        f.supplier_id AS top_future_supplier_id,
        COALESCE(i.supplier_name, f.supplier_id::text) AS top_future_supplier_name,
        COALESCE(i.group_name, i.group_child_name) AS top_future_supplier_group_name,
        f.has_rate_days_30 AS top_future_supplier_has_rate_days_30
    FROM future_supplier_rank f
    LEFT JOIN crm.supplier_info_ods i
      ON f.supplier_id = i.supplier_id
    WHERE f.rn = 1
),

-- 5. 酒店级事实指标。
metrics AS (
    SELECT
        p.metric_end_date,
        p.metric_start_30,
        l.supply_snapshot_date,
        p.assignment_seed,
        f.standard_hotel_id,
        f.hotel_name,
        f.country_code,
        f.country_name,
        f.destination_name,
        f.request_pv_30,
        dt.request_pv_p90 AS high_request_pv_threshold,
        CASE WHEN f.request_pv_30 >= dt.request_pv_p90 THEN 1 ELSE 0 END AS high_request_flag,
        f.available_pv_30,
        f.expose_rp_pv_30,
        f.click_rp_pv_30,
        f.prebook_rp_pv_30,
        f.payment_rp_pv_30,
        f.request_user_cnt_30,
        f.request_client_cnt_30,
        f.request_day_cnt_30,
        f.request_pv_prev7,
        f.request_pv_recent7,
        f.available_pv_prev7,
        f.available_pv_recent7,
        f.country_request_pv_prev7,
        f.country_request_pv_recent7,
        f.destination_request_pv_prev7,
        f.destination_request_pv_recent7,
        ROUND(f.available_pv_30::numeric / NULLIF(f.request_pv_30, 0), 6) AS available_rate_30,
        ROUND(f.available_pv_prev7::numeric / NULLIF(f.request_pv_prev7, 0), 6) AS available_rate_prev7,
        ROUND(f.available_pv_recent7::numeric / NULLIF(f.request_pv_recent7, 0), 6) AS available_rate_recent7,
        ROUND(
            CASE
                WHEN f.country_request_pv_prev7 > 0
                    THEN (f.country_request_pv_recent7 - f.country_request_pv_prev7)::numeric
                         / f.country_request_pv_prev7
                WHEN f.country_request_pv_recent7 > 0 THEN 1
                ELSE 0
            END,
            6
        ) AS country_request_change_7d,
        ROUND(
            CASE
                WHEN f.destination_request_pv_prev7 > 0
                    THEN (f.destination_request_pv_recent7 - f.destination_request_pv_prev7)::numeric
                         / f.destination_request_pv_prev7
                WHEN f.destination_request_pv_recent7 > 0 THEN 1
                ELSE 0
            END,
            6
        ) AS destination_request_change_7d,
        COALESCE(o.valid_bks_30, 0) AS valid_bks_30,
        COALESCE(o.valid_user_cnt_30, 0) AS valid_user_cnt_30,
        COALESCE(o.valid_client_cnt_30, 0) AS valid_client_cnt_30,
        COALESCE(o.valid_supplier_cnt_30, 0) AS valid_supplier_cnt_30,
        COALESCE(o.valid_booking_days_30, 0) AS valid_booking_days_30,
        COALESCE(o.valid_rns_30, 0) AS valid_rns_30,
        COALESCE(o.valid_ttv_cny_30, 0) AS valid_ttv_cny_30,
        COALESCE(o.valid_gp_cny_30, 0) AS valid_gp_cny_30,
        ROUND(o.valid_gp_cny_30 / NULLIF(o.valid_ttv_cny_30, 0) * 100, 4) AS valid_gpr_pct_30,
        ROUND(o.valid_ttv_cny_30 / NULLIF(o.valid_bks_30, 0), 2) AS ttv_per_bk_cny_30,
        ROUND(o.valid_gp_cny_30 / NULLIF(o.valid_bks_30, 0), 2) AS gp_per_bk_cny_30,
        ROUND(o.valid_ttv_cny_30 / NULLIF(o.valid_rns_30, 0), 2) AS adr_cny_30,
        COALESCE(o.gpr_ge10_bks_30, 0) AS gpr_ge10_bks_30,
        ROUND(o.gpr_ge10_bks_30::numeric / NULLIF(o.valid_bks_30, 0), 6) AS gpr_ge10_bks_share_30,
        COALESCE(o.negative_gp_bks_30, 0) AS negative_gp_bks_30,
        COALESCE(d.gpr_valid_days_30, 0) AS gpr_valid_days_30,
        COALESCE(d.gpr_ge10_days_30, 0) AS gpr_ge10_days_30,
        ROUND(d.gpr_ge10_days_30::numeric / NULLIF(d.gpr_valid_days_30, 0), 6) AS gpr_ge10_day_share_30,
        COALESCE(d.negative_gpr_days_30, 0) AS negative_gpr_days_30,
        ROUND(d.min_daily_gpr_30 * 100, 4) AS min_daily_gpr_pct_30,
        COALESCE(a.all_platform_valid_bks_30, 0) AS all_platform_valid_bks_30,
        COALESCE(a.all_platform_valid_ttv_cny_30, 0) AS all_platform_valid_ttv_cny_30,
        COALESCE(a.all_platform_valid_gp_cny_30, 0) AS all_platform_valid_gp_cny_30,
        ROUND(
            0.5 * a.all_platform_valid_gp_cny_30 / NULLIF(a.all_platform_valid_bks_30, 0),
            2
        ) AS all_platform_gp_reference_cny,
        fs.top_future_supplier_id,
        fs.top_future_supplier_name,
        fs.top_future_supplier_group_name,
        COALESCE(fs.top_future_supplier_has_rate_days_30, 0) AS top_future_supplier_has_rate_days_30
    FROM funnel_area f
    CROSS JOIN params p
    CROSS JOIN latest_supply l
    CROSS JOIN demand_threshold dt
    LEFT JOIN shopping_order_agg o
      ON f.standard_hotel_id = o.standard_hotel_id
    LEFT JOIN shopping_daily_agg d
      ON f.standard_hotel_id = d.standard_hotel_id
    LEFT JOIN all_platform_order_agg a
      ON f.standard_hotel_id = a.standard_hotel_id
    LEFT JOIN future_supplier fs
      ON f.standard_hotel_id = fs.standard_hotel_id
    WHERE f.request_pv_30 >= 10
),
banded AS (
    SELECT
        m.*,
        ROUND(m.valid_bks_30::numeric / NULLIF(m.request_pv_30, 0), 6) AS shopping_cvr_30,
        CASE
            WHEN m.adr_cny_30 IS NULL OR m.adr_cny_30 <= 0 THEN 'ADR_UNKNOWN'
            WHEN m.adr_cny_30 < 600 THEN 'ADR_LT_600'
            WHEN m.adr_cny_30 < 1500 THEN 'ADR_600_1499'
            WHEN m.adr_cny_30 < 3000 THEN 'ADR_1500_2999'
            ELSE 'ADR_GE_3000'
        END AS adr_band,
        CASE
            WHEN m.request_pv_30 < 20 THEN 'REQ_10_19'
            WHEN m.request_pv_30 < 50 THEN 'REQ_20_49'
            WHEN m.request_pv_30 < 100 THEN 'REQ_50_99'
            ELSE 'REQ_100_PLUS'
        END AS request_band,
        CASE
            WHEN m.available_rate_30 < 0.80 THEN 'AVAIL_LT_80'
            WHEN m.available_rate_30 < 0.90 THEN 'AVAIL_80_89'
            WHEN m.available_rate_30 < 0.95 THEN 'AVAIL_90_94'
            ELSE 'AVAIL_GE_95'
        END AS availability_band
    FROM metrics m
),

-- 6. 有产酒店同类转化P25/P50：国家×ADR×请求档不足20家时回退。
peer_country AS (
    SELECT
        country_code,
        adr_band,
        request_band,
        COUNT(*) AS peer_hotel_cnt,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY shopping_cvr_30) AS peer_cvr_p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY shopping_cvr_30) AS peer_cvr_p50
    FROM banded
    WHERE valid_bks_30 > 0
    GROUP BY country_code, adr_band, request_band
),
peer_fallback AS (
    SELECT
        adr_band,
        request_band,
        COUNT(*) AS fallback_hotel_cnt,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY shopping_cvr_30) AS fallback_cvr_p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY shopping_cvr_30) AS fallback_cvr_p50
    FROM banded
    WHERE valid_bks_30 > 0
    GROUP BY adr_band, request_band
),
peer_global AS (
    SELECT
        request_band,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY shopping_cvr_30) AS global_cvr_p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY shopping_cvr_30) AS global_cvr_p50
    FROM banded
    WHERE valid_bks_30 > 0
    GROUP BY request_band
),
evaluated AS (
    SELECT
        b.*,
        COALESCE(
            CASE WHEN pc.peer_hotel_cnt >= 20 THEN pc.peer_cvr_p25 END,
            pf.fallback_cvr_p25,
            pg.global_cvr_p25
        ) AS peer_cvr_p25_used,
        COALESCE(
            CASE WHEN pc.peer_hotel_cnt >= 20 THEN pc.peer_cvr_p50 END,
            pf.fallback_cvr_p50,
            pg.global_cvr_p50
        ) AS peer_cvr_p50_used,
        CASE
            WHEN pc.peer_hotel_cnt >= 20 THEN 'COUNTRY_ADR_REQUEST'
            WHEN pf.fallback_hotel_cnt >= 1 THEN 'ADR_REQUEST_FALLBACK'
            ELSE 'REQUEST_GLOBAL_FALLBACK'
        END AS peer_scope,
        CASE
            WHEN b.request_pv_recent7 >= 1
             AND b.request_user_cnt_30 >= 2
             AND b.request_day_cnt_30 >= 2 THEN 1 ELSE 0
        END AS gate_recent_demand,
        CASE WHEN b.available_rate_30 < 0.80 THEN 1 ELSE 0 END AS flag_hist_availability_low,
        CASE WHEN b.top_future_supplier_has_rate_days_30 < 21 THEN 1 ELSE 0 END AS flag_future_supply_low,
        CASE
            WHEN b.request_pv_prev7 >= 5
             AND b.request_pv_recent7 >= 5
             AND COALESCE(b.available_rate_recent7, 0)
                 - COALESCE(b.available_rate_prev7, 0) < -0.05
            THEN 1 ELSE 0
        END AS flag_recent_availability_drop,
        CASE
            WHEN (b.country_request_pv_prev7 >= 100 AND b.country_request_change_7d < -0.20)
              OR (b.destination_request_pv_prev7 >= 30 AND b.destination_request_change_7d < -0.20)
            THEN 1 ELSE 0
        END AS flag_destination_demand_down,
        CASE
            WHEN b.valid_gpr_pct_30 BETWEEN 1.5 AND 50
             AND b.negative_gp_bks_30 = 0
             AND b.negative_gpr_days_30 = 0
             AND COALESCE(b.min_daily_gpr_pct_30, 0) >= 0
             AND b.gp_per_bk_cny_30 - 0.015 * b.ttv_per_bk_cny_30 >= 5
            THEN 1 ELSE 0
        END AS profit_light_eligible,
        CASE
            WHEN b.valid_gpr_pct_30 BETWEEN 3 AND 50
             AND b.negative_gp_bks_30 = 0
             AND b.negative_gpr_days_30 = 0
             AND COALESCE(b.min_daily_gpr_pct_30, 0) >= 0
             AND b.gp_per_bk_cny_30 - 0.020 * b.ttv_per_bk_cny_30 >= 10
            THEN 1 ELSE 0
        END AS profit_standard_eligible,
        CASE
            WHEN b.valid_gpr_pct_30 BETWEEN 10 AND 50
             AND b.negative_gp_bks_30 = 0
             AND b.negative_gpr_days_30 = 0
             AND COALESCE(b.min_daily_gpr_pct_30, 0) >= 0
             AND b.gpr_ge10_bks_share_30 >= 0.90
             AND b.gpr_ge10_day_share_30 >= 0.90
             AND b.gp_per_bk_cny_30 - 0.020 * b.ttv_per_bk_cny_30 >= 20
            THEN 1 ELSE 0
        END AS profit_strong_eligible
    FROM banded b
    LEFT JOIN peer_country pc
      ON b.country_code = pc.country_code
     AND b.adr_band = pc.adr_band
     AND b.request_band = pc.request_band
    LEFT JOIN peer_fallback pf
      ON b.adr_band = pf.adr_band
     AND b.request_band = pf.request_band
    LEFT JOIN peer_global pg
      ON b.request_band = pg.request_band
),

-- 7. 固定优先级MECE分流：第一条命中后停止。
classified AS (
    SELECT
        e.*,
        CASE
            WHEN e.gate_recent_demand = 0
                THEN '1 观察：近期需求不稳定'
            WHEN e.flag_hist_availability_low = 1
                THEN '2 资源修复：近30天有价率不足'
            WHEN e.flag_future_supply_low = 1
                THEN '3 资源修复：未来30天可售不足'
            WHEN e.flag_recent_availability_drop = 1
                THEN '4 资源修复：最近7天有价率下降'
            WHEN e.flag_destination_demand_down = 1
                THEN '5 观察：国家/目的地需求下降'
            WHEN e.valid_bks_30 <= 0
             AND e.all_platform_valid_bks_30 > 0
             AND COALESCE(e.all_platform_gp_reference_cny, 0) < 5
                THEN '6 利润修复：无产但全平台GP不足'
            WHEN e.valid_bks_30 <= 0
                THEN '7 实验候选：有价无产'
            WHEN e.shopping_cvr_30 < e.peer_cvr_p50_used
             AND e.profit_light_eligible = 0
                THEN '8 利润修复：有产低转化但GP不足'
            WHEN e.shopping_cvr_30 < e.peer_cvr_p50_used
                THEN '9 实验候选：有产低转化'
            ELSE '10 排除：转化正常或较高'
        END AS mece_class
    FROM evaluated e
),
typed AS (
    SELECT
        c.*,
        CASE
            WHEN c.mece_class = '7 实验候选：有价无产'
             AND (c.prebook_rp_pv_30 > 0 OR c.payment_rp_pv_30 > 0)
                THEN 'A1 有预订意向但无产'
            WHEN c.mece_class = '7 实验候选：有价无产'
             AND c.click_rp_pv_30 > 0
                THEN 'A2 有点击但无预订'
            WHEN c.mece_class = '7 实验候选：有价无产'
             AND c.all_platform_valid_bks_30 > 0
                THEN 'A3 Shopping无产但全平台有产'
            WHEN c.mece_class = '7 实验候选：有价无产'
                THEN 'A4 仅请求有价、全平台也无产'
            WHEN c.mece_class = '9 实验候选：有产低转化'
             AND c.profit_strong_eligible = 1
             AND c.shopping_cvr_30 < c.peer_cvr_p25_used
                THEN 'B3 极低转化、高GPR低样本'
            WHEN c.mece_class = '9 实验候选：有产低转化'
             AND c.profit_strong_eligible = 1
                THEN 'B3 中低转化、高GPR低样本'
            WHEN c.mece_class = '9 实验候选：有产低转化'
             AND c.profit_standard_eligible = 1
             AND c.shopping_cvr_30 < c.peer_cvr_p25_used
                THEN 'B2 极低转化、标准券可承受'
            WHEN c.mece_class = '9 实验候选：有产低转化'
             AND c.profit_standard_eligible = 1
                THEN 'B2 中低转化、标准券可承受'
            WHEN c.mece_class = '9 实验候选：有产低转化'
             AND c.shopping_cvr_30 < c.peer_cvr_p25_used
                THEN 'B1 极低转化、仅轻促可承受'
            WHEN c.mece_class = '9 实验候选：有产低转化'
                THEN 'B1 中低转化、仅轻促可承受'
            ELSE '不进入实验'
        END AS opportunity_type,
        CASE
            WHEN c.mece_class IN ('7 实验候选：有价无产', '9 实验候选：有产低转化')
                THEN 1 ELSE 0
        END AS experiment_eligible,
        CASE
            WHEN c.valid_bks_30 <= 0 THEN 5
            ELSE GREATEST(
                0,
                LEAST(
                    50,
                    FLOOR(
                        LEAST(
                            0.35 * COALESCE(c.gp_per_bk_cny_30, 0),
                            COALESCE(c.gp_per_bk_cny_30, 0)
                                - 0.02 * COALESCE(c.ttv_per_bk_cny_30, 0)
                        ) / 5.0
                    ) * 5
                )
            )::int
        END AS max_safe_coupon_cny_2pct
    FROM classified c
),
candidate_features AS (
    SELECT
        t.*,
        CASE
            WHEN t.valid_bks_30 <= 0 AND t.all_platform_valid_bks_30 > 0
                THEN 'P0 Shopping无产、全平台有GP参考'
            WHEN t.valid_bks_30 <= 0
                THEN 'P0 Shopping及全平台均无近期GP'
            WHEN t.max_safe_coupon_cny_2pct <= 0
                THEN 'P1 有产但2%GPR护栏下不可发5元'
            WHEN t.max_safe_coupon_cny_2pct = 5
                THEN 'P2 最高5元'
            WHEN t.max_safe_coupon_cny_2pct <= 15
                THEN 'P3 最高10-15元'
            WHEN t.max_safe_coupon_cny_2pct <= 30
                THEN 'P4 最高20-30元'
            WHEN t.max_safe_coupon_cny_2pct < 50
                THEN 'P5 最高35-45元'
            ELSE 'P6 最高50元'
        END AS profit_capacity_band
    FROM typed t
    WHERE t.experiment_eligible = 1
),

-- 8. 分层回退：优先机会类型×利润能力×国家×请求档×ADR档×有价档，样本不足20家时逐级回退。
stratum_counts AS (
    SELECT
        c.*,
        COUNT(*) OVER (
            PARTITION BY opportunity_type, profit_capacity_band,
                         COALESCE(country_code, 'UNK'), request_band, adr_band, availability_band
        ) AS full_stratum_n,
        COUNT(*) OVER (
            PARTITION BY opportunity_type, profit_capacity_band,
                         COALESCE(country_code, 'UNK'), request_band, adr_band
        ) AS middle_stratum_n,
        COUNT(*) OVER (
            PARTITION BY opportunity_type, profit_capacity_band, request_band, adr_band
        ) AS coarse_stratum_n
    FROM candidate_features c
),
candidate_strata AS (
    SELECT
        s.*,
        CASE
            WHEN s.full_stratum_n >= 20 THEN
                s.opportunity_type || '|' || s.profit_capacity_band || '|'
                || COALESCE(s.country_code, 'UNK') || '|' || s.request_band || '|'
                || s.adr_band || '|' || s.availability_band
            WHEN s.middle_stratum_n >= 20 THEN
                s.opportunity_type || '|' || s.profit_capacity_band || '|'
                || COALESCE(s.country_code, 'UNK') || '|' || s.request_band || '|' || s.adr_band
            WHEN s.coarse_stratum_n >= 20 THEN
                s.opportunity_type || '|' || s.profit_capacity_band || '|'
                || s.request_band || '|' || s.adr_band
            ELSE s.opportunity_type || '|' || s.profit_capacity_band
        END AS match_stratum
    FROM stratum_counts s
),
similarity_ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY s.match_stratum
            ORDER BY
                s.request_pv_30 DESC,
                s.request_user_cnt_30 DESC,
                s.request_client_cnt_30 DESC,
                s.request_day_cnt_30 DESC,
                COALESCE(s.available_rate_30, -1) DESC,
                COALESCE(s.shopping_cvr_30, -1),
                s.valid_bks_30,
                COALESCE(s.adr_cny_30, -1),
                MD5(s.standard_hotel_id || '|' || s.assignment_seed)
        ) AS similarity_rank
    FROM candidate_strata s
),
quintet_tagged AS (
    SELECT
        s.*,
        FLOOR((s.similarity_rank - 1) / 5.0)::bigint + 1 AS match_quintet_no
    FROM similarity_ranked s
),
quintet_sized AS (
    SELECT
        q.*,
        COUNT(*) OVER (
            PARTITION BY q.match_stratum, q.match_quintet_no
        ) AS match_quintet_size
    FROM quintet_tagged q
),
complete_quintet_assigned AS (
    SELECT
        q.*,
        NULL::bigint AS remainder_rank,
        ROW_NUMBER() OVER (
            PARTITION BY q.match_stratum, q.match_quintet_no
            ORDER BY MD5(q.standard_hotel_id || '|' || q.assignment_seed || '|group')
        ) - 1 AS group_code
    FROM quintet_sized q
    WHERE q.match_quintet_size = 5
),
remainder_ranked AS (
    SELECT
        q.*,
        ROW_NUMBER() OVER (
            ORDER BY MD5(q.standard_hotel_id || '|' || q.assignment_seed || '|remainder')
        ) AS remainder_rank
    FROM quintet_sized q
    WHERE q.match_quintet_size < 5
),
remainder_assigned AS (
    SELECT
        r.*,
        MOD(r.remainder_rank - 1, 5) AS group_code
    FROM remainder_ranked r
),
assigned_union AS (
    SELECT * FROM complete_quintet_assigned
    UNION ALL
    SELECT * FROM remainder_assigned
),
assigned_labeled AS (
    SELECT
        a.*,
        CASE a.group_code
            WHEN 0 THEN '对照组一（A/A固定对照）'
            WHEN 1 THEN '对照组二（A/A复制对照）'
            WHEN 2 THEN '实验组一（5元轻促）'
            WHEN 3 THEN '实验组二（15元中促）'
            ELSE '实验组三（利润护栏内最高50元）'
        END AS experiment_group,
        CASE a.group_code
            WHEN 0 THEN 0
            WHEN 1 THEN 0
            WHEN 2 THEN 5
            WHEN 3 THEN 15
            ELSE 50
        END AS nominal_coupon_ceiling_cny
    FROM assigned_union a
),
assigned_coupon AS (
    SELECT
        a.*,
        CASE
            WHEN a.group_code IN (0, 1) THEN 0
            WHEN a.valid_bks_30 <= 0 THEN 5
            ELSE LEAST(a.nominal_coupon_ceiling_cny, a.max_safe_coupon_cny_2pct)
        END::int AS recommended_coupon_cny,
        CASE
            WHEN a.group_code IN (0, 1) THEN 0
            WHEN a.valid_bks_30 <= 0 THEN 20
            ELSE 100
        END AS traffic_cap_pct
    FROM assigned_labeled a
),
final_output AS (
    SELECT
        t.*,
        COALESCE(a.experiment_group, '不进入本轮实验') AS experiment_group,
        COALESCE(a.group_code, -1) AS group_code,
        COALESCE(a.nominal_coupon_ceiling_cny, 0) AS nominal_coupon_ceiling_cny,
        COALESCE(a.recommended_coupon_cny, 0) AS recommended_coupon_cny,
        COALESCE(a.traffic_cap_pct, 0) AS traffic_cap_pct,
        a.profit_capacity_band,
        a.match_stratum,
        a.match_quintet_no,
        CASE
            WHEN a.valid_bks_30 > 0 AND a.recommended_coupon_cny > 0
                THEN ROUND(
                    100 * (a.gp_per_bk_cny_30 - a.recommended_coupon_cny)
                    / NULLIF(a.ttv_per_bk_cny_30, 0),
                    4
                )
            ELSE NULL
        END AS projected_post_coupon_gpr_pct,
        CASE
            WHEN a.group_code IN (0, 1) THEN '对照组不发券'
            WHEN a.valid_bks_30 <= 0 AND a.all_platform_valid_bks_30 > 0
                THEN 'Shopping无产；仅5元、20%流量，参考全平台GP并执行首3单止损'
            WHEN a.valid_bks_30 <= 0
                THEN 'Shopping及全平台均无近期产量；仅5元、20%流量，执行首3单止损'
            WHEN a.recommended_coupon_cny <= 0
                THEN '有产但利润容量不足；保留ITT分组但实际不发券'
            ELSE '券额不超过名义上限、单均GP的35%，且券后GPR不低于2%'
        END AS coupon_profit_basis
    FROM typed t
    LEFT JOIN assigned_coupon a
      ON t.standard_hotel_id = a.standard_hotel_id
)
SELECT *
FROM final_output
ORDER BY
    experiment_eligible DESC,
    experiment_group,
    opportunity_type,
    request_pv_30 DESC,
    standard_hotel_id;

-- 使用方式：
-- 1. 最终促销清单：在最外层SELECT增加 WHERE experiment_eligible = 1。
-- 2. 资源修复清单：WHERE mece_class LIKE '2 %' OR mece_class LIKE '3 %' OR mece_class LIKE '4 %'。
-- 3. 观察/利润治理：按mece_class筛选1、5、6、8类。
-- 4. 高请求优先清单：WHERE experiment_eligible = 1 AND high_request_flag = 1。
-- 5. 分组QA：把最后一个SELECT替换为以下查询：
-- SELECT
--     experiment_group,
--     COUNT(*) AS hotel_cnt,
--     SUM(request_pv_30) AS request_pv_30,
--     SUM(valid_bks_30) AS valid_bks_30,
--     SUM(valid_ttv_cny_30) AS valid_ttv_cny_30,
--     SUM(valid_gp_cny_30) AS valid_gp_cny_30,
--     SUM(valid_bks_30)::numeric / NULLIF(SUM(request_pv_30), 0) AS request_to_bks_rate_30,
--     SUM(valid_gp_cny_30) / NULLIF(SUM(valid_ttv_cny_30), 0) AS weighted_gpr_30,
--     AVG(available_rate_30) AS avg_available_rate_30,
--     AVG(recommended_coupon_cny) AS avg_recommended_coupon_cny
-- FROM final_output
-- WHERE experiment_eligible = 1
-- GROUP BY experiment_group
-- ORDER BY experiment_group;
