-- Fleet Service Ops Portal — full database schema (tables, views, constraints).
-- Load into an EMPTY PostgreSQL database:  psql -d fleet_ops_db -f db/schema.sql
-- then add demo data:                      py db/seed_demo.py

--
-- PostgreSQL database dump
--


-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    log_id integer NOT NULL,
    user_id integer,
    action character varying(50) NOT NULL,
    table_name character varying(50),
    record_id integer,
    description text,
    ip_address character varying(45),
    action_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: audit_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_log_id_seq OWNED BY public.audit_log.log_id;


--
-- Name: client_locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.client_locations (
    location_id integer NOT NULL,
    client_name character varying(100) NOT NULL,
    location character varying(100),
    zone character varying(30) NOT NULL,
    tsm_user_id integer,
    is_rental boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: client_locations_location_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.client_locations_location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: client_locations_location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.client_locations_location_id_seq OWNED BY public.client_locations.location_id;


--
-- Name: counter_sale_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.counter_sale_items (
    item_id integer NOT NULL,
    cs_id integer NOT NULL,
    part_id integer NOT NULL,
    quantity integer NOT NULL,
    purchase_rate numeric(10,2) NOT NULL,
    selling_rate numeric(10,2) NOT NULL,
    total_cost numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * purchase_rate)) STORED,
    total_amount numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * selling_rate)) STORED,
    margin numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * (selling_rate - purchase_rate))) STORED,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT counter_sale_items_quantity_check CHECK ((quantity > 0))
);


--
-- Name: TABLE counter_sale_items; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.counter_sale_items IS 'Line items for each counter sale';


--
-- Name: counter_sale_items_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.counter_sale_items_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: counter_sale_items_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.counter_sale_items_item_id_seq OWNED BY public.counter_sale_items.item_id;


--
-- Name: counter_sales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.counter_sales (
    cs_id integer NOT NULL,
    cs_number character varying(20) NOT NULL,
    cs_date date NOT NULL,
    b2b_partner character varying(100) NOT NULL,
    dispatch_location character varying(200),
    dispatched_by character varying(100),
    courier_type character varying(100),
    courier_tracking character varying(100),
    total_amount numeric(12,2) DEFAULT 0,
    status character varying(20) DEFAULT 'Dispatched'::character varying,
    remarks text,
    created_by integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    courier_charges numeric(10,2) DEFAULT 0,
    CONSTRAINT counter_sales_status_check CHECK (((status)::text = ANY (ARRAY[('Dispatched'::character varying)::text, ('In Transit'::character varying)::text, ('Delivered'::character varying)::text, ('Cancelled'::character varying)::text])))
);


--
-- Name: TABLE counter_sales; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.counter_sales IS 'B2B partner parts dispatch transactions';


--
-- Name: COLUMN counter_sales.cs_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.counter_sales.cs_number IS 'Auto-generated: CS-YYYY-NNN';


--
-- Name: counter_sales_cs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.counter_sales_cs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: counter_sales_cs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.counter_sales_cs_id_seq OWNED BY public.counter_sales.cs_id;


--
-- Name: dealer_ticket_no_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dealer_ticket_no_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dealer_tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dealer_tickets (
    id integer NOT NULL,
    ticket_no character varying(20) DEFAULT ('TK-'::text || lpad((nextval('public.dealer_ticket_no_seq'::regclass))::text, 4, '0'::text)) NOT NULL,
    client_name character varying(100) NOT NULL,
    store character varying(150),
    client_location_id integer,
    chassis_number character varying(40),
    complaint_type character varying(60),
    description text NOT NULL,
    contact character varying(100),
    photo_path text,
    status character varying(20) DEFAULT 'OPEN'::character varying NOT NULL,
    job_card_id integer,
    link_method character varying(10),
    customer_remark text,
    internal_note text,
    raised_by integer,
    raised_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'Asia/Kolkata'::text) NOT NULL,
    resolved_by integer,
    resolved_at timestamp without time zone,
    updated_by integer,
    updated_at timestamp without time zone,
    CONSTRAINT dealer_tickets_status_check CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'IN PROGRESS'::character varying, 'RESOLVED'::character varying])::text[])))
);


--
-- Name: dealer_tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dealer_tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dealer_tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dealer_tickets_id_seq OWNED BY public.dealer_tickets.id;


--
-- Name: dealer_vehicles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dealer_vehicles (
    id integer NOT NULL,
    client_name character varying(100) NOT NULL,
    chassis_number character varying(40) NOT NULL,
    store character varying(150),
    is_active boolean DEFAULT true NOT NULL,
    note character varying(200),
    updated_by integer,
    updated_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'Asia/Kolkata'::text) NOT NULL,
    CONSTRAINT dealer_vehicles_chassis_clean CHECK (((chassis_number)::text = upper(replace((chassis_number)::text, ' '::text, ''::text))))
);


--
-- Name: dealer_vehicles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dealer_vehicles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dealer_vehicles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dealer_vehicles_id_seq OWNED BY public.dealer_vehicles.id;


--
-- Name: form_job_cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.form_job_cards (
    id integer NOT NULL,
    job_type character varying(10) NOT NULL,
    job_card_no character varying(30) NOT NULL,
    submitted_at timestamp without time zone,
    job_open_date date,
    client_name character varying(100),
    client_location character varying(150),
    client_location_id integer,
    service_type character varying(60),
    chassis_number character varying(40),
    odo_km character varying(20),
    technician character varying(60),
    field_observation text,
    form_job_status character varying(30),
    completion_date date,
    form jsonb DEFAULT '{}'::jsonb NOT NULL,
    tsm_job_status character varying(30),
    complaint_category character varying(20),
    tsm_observation text,
    repeat_complaints text,
    action_date date,
    rca text,
    spares_cost numeric(12,2),
    labor_cost numeric(12,2),
    warranty_status character varying(60),
    warranty_spares_cost numeric(12,2),
    warranty_labor_cost numeric(12,2),
    updated_by integer,
    updated_at timestamp without time zone,
    excel_pending boolean DEFAULT false NOT NULL,
    excel_error text,
    synced_at timestamp without time zone DEFAULT now() NOT NULL,
    unpriced_parts text,
    CONSTRAINT form_job_cards_job_type_check CHECK (((job_type)::text = ANY (ARRAY[('B2B'::character varying)::text, ('Rental'::character varying)::text])))
);


--
-- Name: form_job_cards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.form_job_cards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: form_job_cards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.form_job_cards_id_seq OWNED BY public.form_job_cards.id;


--
-- Name: inv_moves; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inv_moves (
    id integer NOT NULL,
    hub character varying(10) NOT NULL,
    direction character varying(3) NOT NULL,
    move_date date,
    part_code character varying(40) NOT NULL,
    qty integer NOT NULL,
    unit_cost numeric(12,2),
    source character varying(80),
    ref_no character varying(80),
    purpose character varying(80),
    issued_for character varying(100),
    technician character varying(80),
    chassis_number character varying(40),
    revenue_amt numeric(12,2),
    remarks text,
    in_charge character varying(80),
    transfer_id integer,
    job_card_id integer,
    origin character varying(10) DEFAULT 'portal'::character varying NOT NULL,
    excel_row integer,
    excel_pending boolean DEFAULT false NOT NULL,
    excel_error text,
    created_by integer,
    created_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'Asia/Kolkata'::text) NOT NULL,
    CONSTRAINT inv_moves_direction_check CHECK (((direction)::text = ANY ((ARRAY['IN'::character varying, 'OUT'::character varying])::text[]))),
    CONSTRAINT inv_moves_origin_check CHECK (((origin)::text = ANY ((ARRAY['excel'::character varying, 'portal'::character varying])::text[]))),
    CONSTRAINT inv_moves_qty_check CHECK ((qty > 0))
);


--
-- Name: inv_moves_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inv_moves_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inv_moves_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inv_moves_id_seq OWNED BY public.inv_moves.id;


--
-- Name: inv_parts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inv_parts (
    part_code character varying(40) NOT NULL,
    description character varying(200) NOT NULL,
    hsn character varying(20),
    landing_cost numeric(12,2),
    margin numeric(6,4),
    customer_price numeric(12,2),
    gst numeric(6,4),
    reorder_level integer DEFAULT 10 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    in_excel boolean DEFAULT true NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'Asia/Kolkata'::text) NOT NULL,
    CONSTRAINT inv_parts_code_clean CHECK (((part_code)::text = upper(replace((part_code)::text, ' '::text, ''::text))))
);


--
-- Name: inv_transfer_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inv_transfer_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_cards (
    job_card_id integer NOT NULL,
    job_card_no character varying(30) NOT NULL,
    job_date date NOT NULL,
    vehicle_id integer NOT NULL,
    odometer_reading integer,
    complaint text NOT NULL,
    complaint_category character varying(50),
    technician_id integer,
    inspection_date date,
    expected_delivery date,
    actual_delivery date,
    labour_charges numeric(10,2) DEFAULT 0,
    job_status character varying(30) DEFAULT 'Inspection'::character varying,
    service_type character varying(30),
    remarks text,
    created_by integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    client_location_id integer,
    tsm_observation text,
    closed_by integer,
    closed_at timestamp without time zone,
    CONSTRAINT job_cards_job_status_check CHECK (((job_status)::text = ANY (ARRAY[('Inspection'::character varying)::text, ('Parts Required'::character varying)::text, ('Work In Progress'::character varying)::text, ('Completed'::character varying)::text, ('Delivered'::character varying)::text, ('On Hold'::character varying)::text, ('Cancelled'::character varying)::text, ('Closed'::character varying)::text]))),
    CONSTRAINT job_cards_service_type_check CHECK (((service_type)::text = ANY (ARRAY[('Periodic Maintenance'::character varying)::text, ('Breakdown Repair'::character varying)::text, ('Accident Repair'::character varying)::text, ('Battery Replacement'::character varying)::text, ('Other'::character varying)::text])))
);


--
-- Name: TABLE job_cards; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.job_cards IS 'Maintenance jobs for rental fleet vehicles';


--
-- Name: job_cards_job_card_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.job_cards_job_card_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_cards_job_card_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.job_cards_job_card_id_seq OWNED BY public.job_cards.job_card_id;


--
-- Name: parts_master; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parts_master (
    part_id integer NOT NULL,
    part_code character varying(20) NOT NULL,
    part_name character varying(150) NOT NULL,
    category character varying(50),
    sub_category character varying(50),
    unit character varying(20) DEFAULT 'Nos'::character varying,
    purchase_rate numeric(10,2) NOT NULL,
    internal_rate numeric(10,2) NOT NULL,
    reorder_level integer DEFAULT 5,
    opening_stock integer DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: COLUMN parts_master.internal_rate; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parts_master.internal_rate IS 'Internal billing rate charged to vehicle maintenance account';


--
-- Name: parts_master_part_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.parts_master_part_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: parts_master_part_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.parts_master_part_id_seq OWNED BY public.parts_master.part_id;


--
-- Name: price_master; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.price_master (
    kind character varying(10) NOT NULL,
    name_key character varying(200) NOT NULL,
    name character varying(200) NOT NULL,
    customer_price numeric(12,2),
    landing_cost numeric(12,2),
    labour_charge numeric(12,2),
    synced_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT price_master_kind_check CHECK (((kind)::text = ANY (ARRAY[('spare'::character varying)::text, ('labour'::character varying)::text])))
);


--
-- Name: purchase_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_items (
    item_id integer NOT NULL,
    po_id integer NOT NULL,
    part_id integer NOT NULL,
    quantity integer NOT NULL,
    purchase_rate numeric(10,2) NOT NULL,
    total_amount numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * purchase_rate)) STORED,
    received_qty integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT purchase_order_items_quantity_check CHECK ((quantity > 0))
);


--
-- Name: purchase_order_items_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_items_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_items_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_items_item_id_seq OWNED BY public.purchase_order_items.item_id;


--
-- Name: purchase_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_orders (
    po_id integer NOT NULL,
    po_number character varying(50) NOT NULL,
    po_date date NOT NULL,
    supplier character varying(100) DEFAULT 'OEM'::character varying,
    total_amount numeric(12,2) DEFAULT 0,
    status character varying(20) DEFAULT 'Raised'::character varying,
    remarks text,
    created_by integer,
    received_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT purchase_orders_status_check CHECK (((status)::text = ANY (ARRAY[('Raised'::character varying)::text, ('Received'::character varying)::text, ('Partially Received'::character varying)::text, ('Cancelled'::character varying)::text])))
);


--
-- Name: purchase_orders_po_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_orders_po_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_orders_po_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_orders_po_id_seq OWNED BY public.purchase_orders.po_id;


--
-- Name: rental_fleet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_fleet (
    vehicle_id integer NOT NULL,
    vehicle_number character varying(20) NOT NULL,
    vehicle_model character varying(50) NOT NULL,
    chassis_number character varying(50),
    motor_number character varying(50),
    battery_type character varying(30),
    purchase_date date,
    purchase_cost numeric(12,2),
    current_odometer_km integer DEFAULT 0,
    fleet_status character varying(20) DEFAULT 'Active'::character varying,
    current_renter_name character varying(100),
    current_renter_phone character varying(15),
    rental_start_date date,
    monthly_rental_amount numeric(10,2),
    last_service_date date,
    next_service_due_date date,
    total_maintenance_cost numeric(12,2) DEFAULT 0,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rental_fleet_fleet_status_check CHECK (((fleet_status)::text = ANY (ARRAY[('Active'::character varying)::text, ('Available'::character varying)::text, ('Under Service'::character varying)::text, ('Inactive'::character varying)::text, ('Retired'::character varying)::text])))
);


--
-- Name: TABLE rental_fleet; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.rental_fleet IS 'Rental EV vehicles — the heart of the system';


--
-- Name: COLUMN rental_fleet.fleet_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rental_fleet.fleet_status IS 'Active=rented, Available=ready, UnderService=in workshop';


--
-- Name: rental_fleet_vehicle_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rental_fleet_vehicle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rental_fleet_vehicle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rental_fleet_vehicle_id_seq OWNED BY public.rental_fleet.vehicle_id;


--
-- Name: stock_hubs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_hubs (
    hub character varying(10) NOT NULL,
    name character varying(60) NOT NULL,
    excel_file character varying(200),
    excel_name character varying(60),
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: stock_in; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_in (
    stock_in_id integer NOT NULL,
    received_date date NOT NULL,
    part_id integer NOT NULL,
    quantity integer NOT NULL,
    purchase_rate numeric(10,2) NOT NULL,
    total_value numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * purchase_rate)) STORED,
    oem_invoice_no character varying(50),
    oem_invoice_date date,
    received_by integer,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    source character varying(20) DEFAULT 'OEM'::character varying,
    vendor_name character varying(100),
    CONSTRAINT stock_in_quantity_check CHECK ((quantity > 0))
);


--
-- Name: stock_in_stock_in_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stock_in_stock_in_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stock_in_stock_in_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stock_in_stock_in_id_seq OWNED BY public.stock_in.stock_in_id;


--
-- Name: stock_out; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_out (
    stock_out_id integer NOT NULL,
    issue_date date NOT NULL,
    job_card_id integer NOT NULL,
    vehicle_id integer NOT NULL,
    part_id integer NOT NULL,
    quantity integer NOT NULL,
    purchase_rate numeric(10,2) NOT NULL,
    internal_rate numeric(10,2) NOT NULL,
    total_cost numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * purchase_rate)) STORED,
    total_billing numeric(12,2) GENERATED ALWAYS AS (((quantity)::numeric * internal_rate)) STORED,
    technician_id integer,
    issued_by integer,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT stock_out_quantity_check CHECK ((quantity > 0))
);


--
-- Name: COLUMN stock_out.total_cost; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.stock_out.total_cost IS 'Actual cost (FleetCo''s expense)';


--
-- Name: COLUMN stock_out.total_billing; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.stock_out.total_billing IS 'Internal billing to vehicle maintenance account';


--
-- Name: stock_out_stock_out_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stock_out_stock_out_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stock_out_stock_out_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stock_out_stock_out_id_seq OWNED BY public.stock_out.stock_out_id;


--
-- Name: sync_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_state (
    name character varying(40) NOT NULL,
    last_run timestamp without time zone,
    message text
);


--
-- Name: technicians; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.technicians (
    tech_id integer NOT NULL,
    tech_code character varying(20) NOT NULL,
    tech_name character varying(100) NOT NULL,
    phone character varying(15),
    email character varying(100),
    designation character varying(50),
    specialization character varying(100),
    date_of_joining date,
    monthly_salary numeric(10,2),
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: technicians_tech_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.technicians_tech_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: technicians_tech_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.technicians_tech_id_seq OWNED BY public.technicians.tech_id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(100) NOT NULL,
    email character varying(100),
    phone character varying(15),
    role character varying(30) NOT NULL,
    is_active boolean DEFAULT true,
    last_login timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    zone character varying(30),
    must_change_password boolean DEFAULT true,
    dealer_client character varying(100),
    dealer_store character varying(150),
    failed_logins integer DEFAULT 0 NOT NULL,
    locked_until timestamp without time zone,
    stock_hub character varying(10),
    CONSTRAINT users_dealer_client_check CHECK ((((role)::text <> 'Dealer'::text) OR (dealer_client IS NOT NULL))),
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['Super Admin'::character varying, 'Service Head'::character varying, 'Area Service Manager'::character varying, 'Store Incharge'::character varying, 'Territory Manager'::character varying, 'Dealer'::character varying])::text[])))
);


--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.users IS 'Portal users — Central Hub team only';


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: v_current_stock; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_current_stock AS
 SELECT part_id,
    part_code,
    part_name,
    category,
    unit,
    purchase_rate,
    internal_rate,
    reorder_level,
    opening_stock,
    COALESCE(( SELECT sum(si.quantity) AS sum
           FROM public.stock_in si
          WHERE (si.part_id = p.part_id)), (0)::bigint) AS total_received,
    COALESCE(( SELECT sum(so.quantity) AS sum
           FROM public.stock_out so
          WHERE (so.part_id = p.part_id)), (0)::bigint) AS total_issued,
    ((opening_stock + COALESCE(( SELECT sum(si.quantity) AS sum
           FROM public.stock_in si
          WHERE (si.part_id = p.part_id)), (0)::bigint)) - COALESCE(( SELECT sum(so.quantity) AS sum
           FROM public.stock_out so
          WHERE (so.part_id = p.part_id)), (0)::bigint)) AS current_stock,
        CASE
            WHEN (((opening_stock + COALESCE(( SELECT sum(si.quantity) AS sum
               FROM public.stock_in si
              WHERE (si.part_id = p.part_id)), (0)::bigint)) - COALESCE(( SELECT sum(so.quantity) AS sum
               FROM public.stock_out so
              WHERE (so.part_id = p.part_id)), (0)::bigint)) = 0) THEN 'OUT OF STOCK'::text
            WHEN (((opening_stock + COALESCE(( SELECT sum(si.quantity) AS sum
               FROM public.stock_in si
              WHERE (si.part_id = p.part_id)), (0)::bigint)) - COALESCE(( SELECT sum(so.quantity) AS sum
               FROM public.stock_out so
              WHERE (so.part_id = p.part_id)), (0)::bigint)) <= reorder_level) THEN 'LOW STOCK'::text
            ELSE 'IN STOCK'::text
        END AS stock_status
   FROM public.parts_master p;


--
-- Name: vehicle_downtime; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_downtime (
    downtime_id integer NOT NULL,
    vehicle_id integer NOT NULL,
    job_card_id integer,
    downtime_start timestamp without time zone NOT NULL,
    downtime_end timestamp without time zone,
    downtime_hours numeric(8,2) GENERATED ALWAYS AS (
CASE
    WHEN (downtime_end IS NULL) THEN NULL::numeric
    ELSE (EXTRACT(epoch FROM (downtime_end - downtime_start)) / 3600.0)
END) STORED,
    reason character varying(50),
    revenue_loss numeric(10,2),
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE vehicle_downtime; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.vehicle_downtime IS 'Track every hour a vehicle is out of service = lost revenue';


--
-- Name: v_downtime_analysis; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_downtime_analysis AS
 SELECT f.vehicle_number,
    f.vehicle_model,
    count(d.downtime_id) AS total_downtime_incidents,
    round(COALESCE(sum(d.downtime_hours), (0)::numeric), 2) AS total_downtime_hours,
    COALESCE(sum(d.revenue_loss), (0)::numeric) AS total_revenue_loss
   FROM (public.rental_fleet f
     LEFT JOIN public.vehicle_downtime d ON ((f.vehicle_id = d.vehicle_id)))
  GROUP BY f.vehicle_id, f.vehicle_number, f.vehicle_model
 HAVING (count(d.downtime_id) > 0)
  ORDER BY (round(COALESCE(sum(d.downtime_hours), (0)::numeric), 2)) DESC;


--
-- Name: v_fleet_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fleet_overview AS
 SELECT fleet_status,
    count(*) AS vehicle_count,
    round((((count(*))::numeric * 100.0) / (( SELECT count(*) AS count
           FROM public.rental_fleet rental_fleet_1))::numeric), 1) AS pct_of_fleet,
    sum(monthly_rental_amount) AS total_monthly_rental_potential
   FROM public.rental_fleet
  GROUP BY fleet_status
  ORDER BY (count(*)) DESC;


--
-- Name: v_job_card_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_job_card_summary AS
 SELECT j.job_card_id,
    j.job_card_no,
    j.job_date,
    f.vehicle_number,
    f.vehicle_model,
    j.complaint,
    j.complaint_category,
    j.service_type,
    j.job_status,
    t.tech_name AS technician,
    j.labour_charges,
    COALESCE(( SELECT sum(so.total_cost) AS sum
           FROM public.stock_out so
          WHERE (so.job_card_id = j.job_card_id)), (0)::numeric) AS parts_cost,
    COALESCE(( SELECT sum(so.total_billing) AS sum
           FROM public.stock_out so
          WHERE (so.job_card_id = j.job_card_id)), (0)::numeric) AS parts_billing,
    (j.labour_charges + COALESCE(( SELECT sum(so.total_billing) AS sum
           FROM public.stock_out so
          WHERE (so.job_card_id = j.job_card_id)), (0)::numeric)) AS total_billing
   FROM ((public.job_cards j
     LEFT JOIN public.rental_fleet f ON ((j.vehicle_id = f.vehicle_id)))
     LEFT JOIN public.technicians t ON ((j.technician_id = t.tech_id)));


--
-- Name: v_monthly_cost; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_monthly_cost AS
 SELECT to_char((j.job_date)::timestamp with time zone, 'YYYY-MM'::text) AS month,
    count(j.job_card_id) AS total_jobs,
    count(DISTINCT j.vehicle_id) AS unique_vehicles_serviced,
    sum(j.labour_charges) AS labour_cost,
    COALESCE(sum(jcs.parts_billing), (0)::numeric) AS parts_cost,
    (sum(j.labour_charges) + COALESCE(sum(jcs.parts_billing), (0)::numeric)) AS total_cost
   FROM (public.job_cards j
     LEFT JOIN public.v_job_card_summary jcs ON ((j.job_card_id = jcs.job_card_id)))
  GROUP BY (to_char((j.job_date)::timestamp with time zone, 'YYYY-MM'::text))
  ORDER BY (to_char((j.job_date)::timestamp with time zone, 'YYYY-MM'::text)) DESC;


--
-- Name: v_technician_performance; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_technician_performance AS
SELECT
    NULL::integer AS tech_id,
    NULL::character varying(20) AS tech_code,
    NULL::character varying(100) AS tech_name,
    NULL::character varying(100) AS specialization,
    NULL::bigint AS total_jobs,
    NULL::bigint AS completed_jobs,
    NULL::bigint AS pending_jobs,
    NULL::numeric AS total_billing_generated;


--
-- Name: v_top_failing_components; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_top_failing_components AS
 SELECT complaint_category,
    count(*) AS occurrence_count,
    count(DISTINCT vehicle_id) AS unique_vehicles_affected,
    round((((count(*))::numeric * 100.0) / (( SELECT count(*) AS count
           FROM public.job_cards job_cards_1))::numeric), 1) AS pct_of_total_jobs
   FROM public.job_cards
  WHERE (complaint_category IS NOT NULL)
  GROUP BY complaint_category
  ORDER BY (count(*)) DESC;


--
-- Name: v_vehicle_maintenance_history; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_vehicle_maintenance_history AS
SELECT
    NULL::integer AS vehicle_id,
    NULL::character varying(20) AS vehicle_number,
    NULL::character varying(50) AS vehicle_model,
    NULL::integer AS current_odometer_km,
    NULL::character varying(20) AS fleet_status,
    NULL::bigint AS total_services,
    NULL::numeric AS total_maintenance_cost,
    NULL::date AS last_service_date,
    NULL::date AS next_service_due_date;


--
-- Name: vehicle_downtime_downtime_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_downtime_downtime_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_downtime_downtime_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_downtime_downtime_id_seq OWNED BY public.vehicle_downtime.downtime_id;


--
-- Name: audit_log log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN log_id SET DEFAULT nextval('public.audit_log_log_id_seq'::regclass);


--
-- Name: client_locations location_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_locations ALTER COLUMN location_id SET DEFAULT nextval('public.client_locations_location_id_seq'::regclass);


--
-- Name: counter_sale_items item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sale_items ALTER COLUMN item_id SET DEFAULT nextval('public.counter_sale_items_item_id_seq'::regclass);


--
-- Name: counter_sales cs_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sales ALTER COLUMN cs_id SET DEFAULT nextval('public.counter_sales_cs_id_seq'::regclass);


--
-- Name: dealer_tickets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets ALTER COLUMN id SET DEFAULT nextval('public.dealer_tickets_id_seq'::regclass);


--
-- Name: dealer_vehicles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_vehicles ALTER COLUMN id SET DEFAULT nextval('public.dealer_vehicles_id_seq'::regclass);


--
-- Name: form_job_cards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_job_cards ALTER COLUMN id SET DEFAULT nextval('public.form_job_cards_id_seq'::regclass);


--
-- Name: inv_moves id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_moves ALTER COLUMN id SET DEFAULT nextval('public.inv_moves_id_seq'::regclass);


--
-- Name: job_cards job_card_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards ALTER COLUMN job_card_id SET DEFAULT nextval('public.job_cards_job_card_id_seq'::regclass);


--
-- Name: parts_master part_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parts_master ALTER COLUMN part_id SET DEFAULT nextval('public.parts_master_part_id_seq'::regclass);


--
-- Name: purchase_order_items item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items ALTER COLUMN item_id SET DEFAULT nextval('public.purchase_order_items_item_id_seq'::regclass);


--
-- Name: purchase_orders po_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders ALTER COLUMN po_id SET DEFAULT nextval('public.purchase_orders_po_id_seq'::regclass);


--
-- Name: rental_fleet vehicle_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_fleet ALTER COLUMN vehicle_id SET DEFAULT nextval('public.rental_fleet_vehicle_id_seq'::regclass);


--
-- Name: stock_in stock_in_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_in ALTER COLUMN stock_in_id SET DEFAULT nextval('public.stock_in_stock_in_id_seq'::regclass);


--
-- Name: stock_out stock_out_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out ALTER COLUMN stock_out_id SET DEFAULT nextval('public.stock_out_stock_out_id_seq'::regclass);


--
-- Name: technicians tech_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.technicians ALTER COLUMN tech_id SET DEFAULT nextval('public.technicians_tech_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: vehicle_downtime downtime_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_downtime ALTER COLUMN downtime_id SET DEFAULT nextval('public.vehicle_downtime_downtime_id_seq'::regclass);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (log_id);


--
-- Name: client_locations client_locations_client_name_location_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_locations
    ADD CONSTRAINT client_locations_client_name_location_key UNIQUE (client_name, location);


--
-- Name: client_locations client_locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_locations
    ADD CONSTRAINT client_locations_pkey PRIMARY KEY (location_id);


--
-- Name: counter_sale_items counter_sale_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sale_items
    ADD CONSTRAINT counter_sale_items_pkey PRIMARY KEY (item_id);


--
-- Name: counter_sales counter_sales_cs_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sales
    ADD CONSTRAINT counter_sales_cs_number_key UNIQUE (cs_number);


--
-- Name: counter_sales counter_sales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sales
    ADD CONSTRAINT counter_sales_pkey PRIMARY KEY (cs_id);


--
-- Name: dealer_tickets dealer_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_pkey PRIMARY KEY (id);


--
-- Name: dealer_tickets dealer_tickets_ticket_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_ticket_no_key UNIQUE (ticket_no);


--
-- Name: dealer_vehicles dealer_vehicles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_pkey PRIMARY KEY (id);


--
-- Name: form_job_cards form_job_cards_job_type_job_card_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_job_cards
    ADD CONSTRAINT form_job_cards_job_type_job_card_no_key UNIQUE (job_type, job_card_no);


--
-- Name: form_job_cards form_job_cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_job_cards
    ADD CONSTRAINT form_job_cards_pkey PRIMARY KEY (id);


--
-- Name: inv_moves inv_moves_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_moves
    ADD CONSTRAINT inv_moves_pkey PRIMARY KEY (id);


--
-- Name: inv_parts inv_parts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_parts
    ADD CONSTRAINT inv_parts_pkey PRIMARY KEY (part_code);


--
-- Name: job_cards job_cards_job_card_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_job_card_no_key UNIQUE (job_card_no);


--
-- Name: job_cards job_cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_pkey PRIMARY KEY (job_card_id);


--
-- Name: parts_master parts_master_part_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parts_master
    ADD CONSTRAINT parts_master_part_code_key UNIQUE (part_code);


--
-- Name: parts_master parts_master_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parts_master
    ADD CONSTRAINT parts_master_pkey PRIMARY KEY (part_id);


--
-- Name: price_master price_master_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.price_master
    ADD CONSTRAINT price_master_pkey PRIMARY KEY (kind, name_key);


--
-- Name: purchase_order_items purchase_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_pkey PRIMARY KEY (item_id);


--
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (po_id);


--
-- Name: purchase_orders purchase_orders_po_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_po_number_key UNIQUE (po_number);


--
-- Name: rental_fleet rental_fleet_chassis_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_fleet
    ADD CONSTRAINT rental_fleet_chassis_number_key UNIQUE (chassis_number);


--
-- Name: rental_fleet rental_fleet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_fleet
    ADD CONSTRAINT rental_fleet_pkey PRIMARY KEY (vehicle_id);


--
-- Name: rental_fleet rental_fleet_vehicle_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_fleet
    ADD CONSTRAINT rental_fleet_vehicle_number_key UNIQUE (vehicle_number);


--
-- Name: stock_hubs stock_hubs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_hubs
    ADD CONSTRAINT stock_hubs_pkey PRIMARY KEY (hub);


--
-- Name: stock_in stock_in_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_in
    ADD CONSTRAINT stock_in_pkey PRIMARY KEY (stock_in_id);


--
-- Name: stock_out stock_out_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out
    ADD CONSTRAINT stock_out_pkey PRIMARY KEY (stock_out_id);


--
-- Name: sync_state sync_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_state
    ADD CONSTRAINT sync_state_pkey PRIMARY KEY (name);


--
-- Name: technicians technicians_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.technicians
    ADD CONSTRAINT technicians_pkey PRIMARY KEY (tech_id);


--
-- Name: technicians technicians_tech_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.technicians
    ADD CONSTRAINT technicians_tech_code_key UNIQUE (tech_code);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: vehicle_downtime vehicle_downtime_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_downtime
    ADD CONSTRAINT vehicle_downtime_pkey PRIMARY KEY (downtime_id);


--
-- Name: dealer_tickets_client_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dealer_tickets_client_idx ON public.dealer_tickets USING btree (lower((client_name)::text), status);


--
-- Name: dealer_tickets_job_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dealer_tickets_job_idx ON public.dealer_tickets USING btree (job_card_id);


--
-- Name: dealer_vehicles_client_chassis; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX dealer_vehicles_client_chassis ON public.dealer_vehicles USING btree (lower((client_name)::text), chassis_number);


--
-- Name: dealer_vehicles_store_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dealer_vehicles_store_idx ON public.dealer_vehicles USING btree (lower((client_name)::text), store);


--
-- Name: form_job_cards_chassis_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX form_job_cards_chassis_idx ON public.form_job_cards USING btree (upper(replace((chassis_number)::text, ' '::text, ''::text)));


--
-- Name: form_job_cards_loc_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX form_job_cards_loc_idx ON public.form_job_cards USING btree (client_location_id);


--
-- Name: form_job_cards_pending_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX form_job_cards_pending_idx ON public.form_job_cards USING btree (excel_pending) WHERE excel_pending;


--
-- Name: idx_cs_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cs_date ON public.counter_sales USING btree (cs_date);


--
-- Name: idx_cs_items_csid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cs_items_csid ON public.counter_sale_items USING btree (cs_id);


--
-- Name: idx_cs_items_part; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cs_items_part ON public.counter_sale_items USING btree (part_id);


--
-- Name: idx_cs_partner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cs_partner ON public.counter_sales USING btree (b2b_partner);


--
-- Name: idx_downtime_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_downtime_vehicle ON public.vehicle_downtime USING btree (vehicle_id);


--
-- Name: idx_fleet_next_service; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fleet_next_service ON public.rental_fleet USING btree (next_service_due_date);


--
-- Name: idx_fleet_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fleet_status ON public.rental_fleet USING btree (fleet_status);


--
-- Name: idx_fleet_vehicle_num; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fleet_vehicle_num ON public.rental_fleet USING btree (vehicle_number);


--
-- Name: idx_jobs_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_jobs_date ON public.job_cards USING btree (job_date);


--
-- Name: idx_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_jobs_status ON public.job_cards USING btree (job_status);


--
-- Name: idx_jobs_technician; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_jobs_technician ON public.job_cards USING btree (technician_id);


--
-- Name: idx_jobs_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_jobs_vehicle ON public.job_cards USING btree (vehicle_id);


--
-- Name: idx_parts_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parts_category ON public.parts_master USING btree (category);


--
-- Name: idx_po_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_po_date ON public.purchase_orders USING btree (po_date);


--
-- Name: idx_po_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_po_status ON public.purchase_orders USING btree (status);


--
-- Name: idx_poi_po_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_poi_po_id ON public.purchase_order_items USING btree (po_id);


--
-- Name: idx_stockin_part; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stockin_part ON public.stock_in USING btree (part_id);


--
-- Name: idx_stockout_part; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stockout_part ON public.stock_out USING btree (part_id);


--
-- Name: idx_stockout_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stockout_vehicle ON public.stock_out USING btree (vehicle_id);


--
-- Name: idx_users_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_role ON public.users USING btree (role);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: inv_moves_chassis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX inv_moves_chassis ON public.inv_moves USING btree (chassis_number);


--
-- Name: inv_moves_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX inv_moves_date ON public.inv_moves USING btree (move_date);


--
-- Name: inv_moves_hub_part; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX inv_moves_hub_part ON public.inv_moves USING btree (hub, part_code);


--
-- Name: inv_moves_job; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX inv_moves_job ON public.inv_moves USING btree (job_card_id);


--
-- Name: inv_moves_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX inv_moves_pending ON public.inv_moves USING btree (excel_pending) WHERE excel_pending;


--
-- Name: users_username_lower_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX users_username_lower_idx ON public.users USING btree (lower((username)::text));


--
-- Name: v_technician_performance _RETURN; Type: RULE; Schema: public; Owner: -
--

CREATE OR REPLACE VIEW public.v_technician_performance AS
 SELECT t.tech_id,
    t.tech_code,
    t.tech_name,
    t.specialization,
    count(j.job_card_id) AS total_jobs,
    count(
        CASE
            WHEN ((j.job_status)::text = 'Completed'::text) THEN 1
            ELSE NULL::integer
        END) AS completed_jobs,
    count(
        CASE
            WHEN ((j.job_status)::text = ANY (ARRAY[('Work In Progress'::character varying)::text, ('Inspection'::character varying)::text, ('Parts Required'::character varying)::text])) THEN 1
            ELSE NULL::integer
        END) AS pending_jobs,
    COALESCE(sum(jcs.total_billing), (0)::numeric) AS total_billing_generated
   FROM ((public.technicians t
     LEFT JOIN public.job_cards j ON ((t.tech_id = j.technician_id)))
     LEFT JOIN public.v_job_card_summary jcs ON ((j.job_card_id = jcs.job_card_id)))
  GROUP BY t.tech_id;


--
-- Name: v_vehicle_maintenance_history _RETURN; Type: RULE; Schema: public; Owner: -
--

CREATE OR REPLACE VIEW public.v_vehicle_maintenance_history AS
 SELECT f.vehicle_id,
    f.vehicle_number,
    f.vehicle_model,
    f.current_odometer_km,
    f.fleet_status,
    count(j.job_card_id) AS total_services,
    (COALESCE(sum(jcs.parts_billing), (0)::numeric) + COALESCE(sum(j.labour_charges), (0)::numeric)) AS total_maintenance_cost,
    max(j.job_date) AS last_service_date,
    f.next_service_due_date
   FROM ((public.rental_fleet f
     LEFT JOIN public.job_cards j ON ((f.vehicle_id = j.vehicle_id)))
     LEFT JOIN ( SELECT stock_out.job_card_id,
            sum(stock_out.total_billing) AS parts_billing
           FROM public.stock_out
          GROUP BY stock_out.job_card_id) jcs ON ((j.job_card_id = jcs.job_card_id)))
  GROUP BY f.vehicle_id;


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: client_locations client_locations_tsm_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_locations
    ADD CONSTRAINT client_locations_tsm_user_id_fkey FOREIGN KEY (tsm_user_id) REFERENCES public.users(user_id);


--
-- Name: counter_sale_items counter_sale_items_cs_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sale_items
    ADD CONSTRAINT counter_sale_items_cs_id_fkey FOREIGN KEY (cs_id) REFERENCES public.counter_sales(cs_id) ON DELETE CASCADE;


--
-- Name: counter_sale_items counter_sale_items_part_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sale_items
    ADD CONSTRAINT counter_sale_items_part_id_fkey FOREIGN KEY (part_id) REFERENCES public.parts_master(part_id);


--
-- Name: counter_sales counter_sales_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.counter_sales
    ADD CONSTRAINT counter_sales_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(user_id);


--
-- Name: dealer_tickets dealer_tickets_client_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_client_location_id_fkey FOREIGN KEY (client_location_id) REFERENCES public.client_locations(location_id);


--
-- Name: dealer_tickets dealer_tickets_job_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_job_card_id_fkey FOREIGN KEY (job_card_id) REFERENCES public.form_job_cards(id);


--
-- Name: dealer_tickets dealer_tickets_raised_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_raised_by_fkey FOREIGN KEY (raised_by) REFERENCES public.users(user_id);


--
-- Name: dealer_tickets dealer_tickets_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(user_id);


--
-- Name: dealer_tickets dealer_tickets_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_tickets
    ADD CONSTRAINT dealer_tickets_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(user_id);


--
-- Name: dealer_vehicles dealer_vehicles_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dealer_vehicles
    ADD CONSTRAINT dealer_vehicles_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(user_id);


--
-- Name: form_job_cards form_job_cards_client_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_job_cards
    ADD CONSTRAINT form_job_cards_client_location_id_fkey FOREIGN KEY (client_location_id) REFERENCES public.client_locations(location_id);


--
-- Name: form_job_cards form_job_cards_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_job_cards
    ADD CONSTRAINT form_job_cards_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(user_id);


--
-- Name: inv_moves inv_moves_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_moves
    ADD CONSTRAINT inv_moves_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(user_id);


--
-- Name: inv_moves inv_moves_hub_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_moves
    ADD CONSTRAINT inv_moves_hub_fkey FOREIGN KEY (hub) REFERENCES public.stock_hubs(hub);


--
-- Name: inv_moves inv_moves_job_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_moves
    ADD CONSTRAINT inv_moves_job_card_id_fkey FOREIGN KEY (job_card_id) REFERENCES public.form_job_cards(id) ON DELETE SET NULL;


--
-- Name: inv_moves inv_moves_part_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_moves
    ADD CONSTRAINT inv_moves_part_code_fkey FOREIGN KEY (part_code) REFERENCES public.inv_parts(part_code) ON UPDATE CASCADE;


--
-- Name: inv_parts inv_parts_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inv_parts
    ADD CONSTRAINT inv_parts_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(user_id);


--
-- Name: job_cards job_cards_client_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_client_location_id_fkey FOREIGN KEY (client_location_id) REFERENCES public.client_locations(location_id);


--
-- Name: job_cards job_cards_closed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES public.users(user_id);


--
-- Name: job_cards job_cards_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(user_id);


--
-- Name: job_cards job_cards_technician_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_technician_id_fkey FOREIGN KEY (technician_id) REFERENCES public.technicians(tech_id);


--
-- Name: job_cards job_cards_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_cards
    ADD CONSTRAINT job_cards_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.rental_fleet(vehicle_id);


--
-- Name: purchase_order_items purchase_order_items_part_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_part_id_fkey FOREIGN KEY (part_id) REFERENCES public.parts_master(part_id);


--
-- Name: purchase_order_items purchase_order_items_po_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_po_id_fkey FOREIGN KEY (po_id) REFERENCES public.purchase_orders(po_id) ON DELETE CASCADE;


--
-- Name: purchase_orders purchase_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(user_id);


--
-- Name: stock_in stock_in_part_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_in
    ADD CONSTRAINT stock_in_part_id_fkey FOREIGN KEY (part_id) REFERENCES public.parts_master(part_id);


--
-- Name: stock_in stock_in_received_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_in
    ADD CONSTRAINT stock_in_received_by_fkey FOREIGN KEY (received_by) REFERENCES public.users(user_id);


--
-- Name: stock_out stock_out_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out
    ADD CONSTRAINT stock_out_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.users(user_id);


--
-- Name: stock_out stock_out_job_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out
    ADD CONSTRAINT stock_out_job_card_id_fkey FOREIGN KEY (job_card_id) REFERENCES public.job_cards(job_card_id);


--
-- Name: stock_out stock_out_part_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out
    ADD CONSTRAINT stock_out_part_id_fkey FOREIGN KEY (part_id) REFERENCES public.parts_master(part_id);


--
-- Name: stock_out stock_out_technician_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out
    ADD CONSTRAINT stock_out_technician_id_fkey FOREIGN KEY (technician_id) REFERENCES public.technicians(tech_id);


--
-- Name: stock_out stock_out_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_out
    ADD CONSTRAINT stock_out_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.rental_fleet(vehicle_id);


--
-- Name: users users_stock_hub_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_stock_hub_fkey FOREIGN KEY (stock_hub) REFERENCES public.stock_hubs(hub);


--
-- Name: vehicle_downtime vehicle_downtime_job_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_downtime
    ADD CONSTRAINT vehicle_downtime_job_card_id_fkey FOREIGN KEY (job_card_id) REFERENCES public.job_cards(job_card_id);


--
-- Name: vehicle_downtime vehicle_downtime_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_downtime
    ADD CONSTRAINT vehicle_downtime_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.rental_fleet(vehicle_id);


--
-- Name: audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: client_locations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.client_locations ENABLE ROW LEVEL SECURITY;

--
-- Name: counter_sale_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.counter_sale_items ENABLE ROW LEVEL SECURITY;

--
-- Name: counter_sales; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.counter_sales ENABLE ROW LEVEL SECURITY;

--
-- Name: dealer_tickets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dealer_tickets ENABLE ROW LEVEL SECURITY;

--
-- Name: dealer_vehicles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dealer_vehicles ENABLE ROW LEVEL SECURITY;

--
-- Name: form_job_cards; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.form_job_cards ENABLE ROW LEVEL SECURITY;

--
-- Name: inv_moves; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.inv_moves ENABLE ROW LEVEL SECURITY;

--
-- Name: inv_parts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.inv_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: job_cards; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.job_cards ENABLE ROW LEVEL SECURITY;

--
-- Name: parts_master; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.parts_master ENABLE ROW LEVEL SECURITY;

--
-- Name: price_master; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.price_master ENABLE ROW LEVEL SECURITY;

--
-- Name: purchase_order_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.purchase_order_items ENABLE ROW LEVEL SECURITY;

--
-- Name: purchase_orders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.purchase_orders ENABLE ROW LEVEL SECURITY;

--
-- Name: rental_fleet; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rental_fleet ENABLE ROW LEVEL SECURITY;

--
-- Name: stock_hubs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.stock_hubs ENABLE ROW LEVEL SECURITY;

--
-- Name: stock_in; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.stock_in ENABLE ROW LEVEL SECURITY;

--
-- Name: stock_out; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.stock_out ENABLE ROW LEVEL SECURITY;

--
-- Name: sync_state; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sync_state ENABLE ROW LEVEL SECURITY;

--
-- Name: technicians; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.technicians ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: vehicle_downtime; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.vehicle_downtime ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--


