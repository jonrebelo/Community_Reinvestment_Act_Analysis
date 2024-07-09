
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from sqlalchemy import create_engine
from great_tables import GT
import numpy as np

def create_db_connection():
    # Create a connection engine to the SQLite database
    return create_engine('sqlite:///my_database.db')

def fetch_bank_names(engine):
    # Query all bank names from the PE_Table
    query = "SELECT DISTINCT bank_name FROM PE_Table;"
    # Use polars to read the SQL query
    df = pl.read_database(query=query, connection=engine.connect())
    return df['bank_name'].unique().to_list()

def fetch_years_for_bank(engine, selected_bank):
    # Query the id_rssd for the selected bank from the PE_Table
    query = f"SELECT id_rssd FROM PE_Table WHERE bank_name = '{selected_bank}';"
    df = pl.read_database(query=query, connection=engine.connect())
    id_rssd = df['id_rssd'][0]
    # Query the available years for the selected bank from the Retail_Table
    query = f"SELECT DISTINCT ActivityYear FROM Retail_Table WHERE id_rssd = {id_rssd};"
    df = pl.read_database(query=query, connection=engine.connect())
    return df['ActivityYear'].unique().to_list()

def fetch_assessment_area(engine, selected_bank, selected_year):
    query = f"SELECT MD_Code, MSA_Code, State_Code, County_Code FROM Retail_Table WHERE id_rssd = (SELECT id_rssd FROM PE_Table WHERE bank_name = '{selected_bank}') AND ActivityYear = {selected_year};"
    df = pl.read_database(query, engine)
    #print(f"Initial query result: {df}")

    assessment_areas = {}

    for row in df.iter_rows():
        md_code, msa_code, state_code, county_code = row
        lookup_method = None  # Reset lookup_method at the start of each loop iteration
        #print(f"Lookup method reset to: {lookup_method}")
        skip_row = False  # Reset skip_row at the start of each loop iteration

        # Look up by MD_Code first
        if md_code is not None and md_code != 'NA':
                #print(f"MD_Code: {md_code}")
                for table in ['2024 tracts', '2022-2023 tracts']:
                    query = f"SELECT `MSA/MD name` FROM `{table}` WHERE `MSA/MD Code` = '{md_code}';"
                    df = pl.read_database(query, engine)
                    if df.height != 0:
                        area_name = df['MSA/MD name'][0]
                        lookup_method = 'md'
                        assessment_areas[area_name] = {'codes': (md_code, msa_code, state_code, county_code, 'md')}
                        #print(f"Used MD_Code {md_code} to look up MSA/MD name {area_name}. Lookup method: {lookup_method}")
                        skip_row = True  # Set skip_row to True if MD_Code lookup was successful
                        break

        # If MD_Code lookup was successful, skip the rest of the current row
        if skip_row:
            #print(f"Skipping row due to successful MD_Code lookup. Current lookup method: {lookup_method}")
            continue

        # If MD_Code lookup failed, try MSA_Code
        if msa_code is not None and msa_code != 'NA':
                #print(f"MSA_Code: {msa_code}")
                for table in ['2024 tracts', '2022-2023 tracts']:
                    query = f"SELECT `MSA/MD name` FROM `{table}` WHERE `MSA/MD Code` = '{msa_code}';"
                    df = pl.read_database(query, engine)
                    if df.height != 0:
                        area_name = df['MSA/MD name'][0]
                        lookup_method = 'msa' 
                        assessment_areas[area_name] = {'codes': (md_code, msa_code, state_code, county_code, 'msa')}
                        #print(f"Used MSA_Code {msa_code} to look up MSA/MD name {area_name}. Lookup method: {lookup_method}")
                        break

        #print(f"After MSA_Code lookup, current lookup method: {lookup_method}")

        # If both MD_Code and MSA_Code lookups failed, try State_Code and County_Code
        if lookup_method != 'md' and lookup_method != 'msa' and str(state_code).isdigit() and str(county_code).isdigit():
            state_code, county_code = map(int, (state_code, county_code))
            #print(f"Looking up by State_Code: {state_code} and County_Code: {county_code}")
            for table in ['2024 tracts', '2022-2023 tracts']:
                query = f"SELECT `County name`, `State` FROM `{table}` WHERE `State code` = {state_code} AND `County code` = {county_code};"
                df = pl.read_database(query, engine)
                if df.height != 0:
                    area_name = f"{df['County name'][0]}, {df['State'][0]}"
                    lookup_method = 'state_county' 
                    assessment_areas[area_name] = {'codes': (md_code, msa_code, state_code, county_code, 'state_county')}
                    #print(f"Used State_Code {state_code} and County_Code {county_code} to look up MSA/MD name {area_name}. Lookup method: {lookup_method}")

        #print(f"After State_Code and County_Code lookup, current lookup method: {lookup_method}")

    if not assessment_areas:
        print("No matching records found")
        return None

    #print(f"Assessment areas: {assessment_areas}")
    return assessment_areas

def fetch_loan_data_loan_dist(engine, selected_bank, selected_year, md_code, msa_code, selected_area, lookup_method, state_code, county_code):

    # Print the values of the variables
    #print(f"Engine: {engine}")
    #print(f"Selected bank: {selected_bank}")
    #print(f"Selected year: {selected_year}")
    #print(f"MD Code: {md_code}")
    #print(f"MSA Code: {msa_code}")
    #print(f"Selected area: {selected_area}")
    #print(f"State Code: {state_code}")
    #print(f"County Code: {county_code}")
    #print(f"Lookup method: {lookup_method}")

    # Query the loan data for the selected bank, year, and assessment area from the Retail_Table
    if lookup_method == 'md':
        #print("Using MD Code for lookup")
        query = f"""
        SELECT 
            Amt_Orig_SFam_Closed, 
            Amt_Orig_SFam_Open, 
            Amt_Orig_MFam, 
            SF_Amt_Orig, 
            SB_Amt_Orig, 
            Amt_Orig,
            Partial_Ind,
            State_Code,
            County_Code 
        FROM Retail_Table 
        WHERE 
            id_rssd = (SELECT id_rssd FROM PE_Table WHERE bank_name = '{selected_bank}') 
            AND ActivityYear = {selected_year} 
            AND MD_Code = '{md_code}';
        """
    elif lookup_method == 'msa':
        #print("Using MSA Code for lookup")
        query = f"""
        SELECT 
            Amt_Orig_SFam_Closed, 
            Amt_Orig_SFam_Open, 
            Amt_Orig_MFam, 
            SF_Amt_Orig, 
            SB_Amt_Orig, 
            Amt_Orig,
            Partial_Ind,
            State_Code,
            County_Code 
        FROM Retail_Table 
        WHERE 
            id_rssd = (SELECT id_rssd FROM PE_Table WHERE bank_name = '{selected_bank}') 
            AND ActivityYear = {selected_year} 
            AND MSA_Code = '{msa_code}';
        """
    else:  # lookup_method == 'state_county'
        #print("Using State and County Code for lookup")
        query = f"""
        SELECT 
            Amt_Orig_SFam_Closed, 
            Amt_Orig_SFam_Open, 
            Amt_Orig_MFam, 
            SF_Amt_Orig, 
            SB_Amt_Orig, 
            Amt_Orig,
            Partial_Ind,
            State_Code,
            County_Code 
        FROM Retail_Table 
        WHERE 
            id_rssd = (SELECT id_rssd FROM PE_Table WHERE bank_name = '{selected_bank}') 
            AND ActivityYear = {selected_year} 
            AND State_Code = {state_code} AND County_Code = {county_code};
        """
    df = pl.read_database(query, engine)

    # Print the first few rows of the DataFrame
    print(df.head())

    return df

def create_loan_distribution_chart(df, area_name, engine):
    def process_row(partial_ind, state_code, county_code):
        if partial_ind == 'Y':
            county_name = None
            for table in ['2024 tracts', '2022-2023 tracts']:
                query = f"SELECT `County name`, `State` FROM `{table}` WHERE `State code` = {state_code} AND `County code` = {county_code};"
                df_lookup = pl.read_database(query, engine)
                if df_lookup.height != 0:
                    county_name = df_lookup['County name'][0]
                    break
            if county_name is not None:
                label = f"{county_name}"
                return label
        return None

    df = df.with_columns([
        pl.struct(['Partial_Ind', 'State_Code', 'County_Code']).map_elements(lambda x: process_row(x['Partial_Ind'], x['State_Code'], x['County_Code'])).alias('label')
    ])

    df = df.with_columns([
        (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
         pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')).alias('Total Gross Loans')
    ])

    df_chart = df.drop(['Partial_Ind', 'State_Code', 'County_Code'])

    figures = []

    variable_mapping = {
        'Amt_Orig_SFam_Closed': '1-4 Family Closed-End',
        'Amt_Orig_SFam_Open': '1-4 Family Revolving',
        'Amt_Orig_MFam': 'Multi-Family',
        'SF_Amt_Orig': 'Farm Loans',
        'SB_Amt_Orig': 'Small Business Loans',
        'Amt_Orig': 'Total Mortgage Loan Amount',
        'Total Gross Loans': 'Total Gross Loans'
    }

    if df_chart.height > 1:
        for row in df_chart.iter_rows():
            row_data = list(row)
            label = row_data[df_chart.columns.index('label')]
            row_data.pop(df_chart.columns.index('label'))
            if label is not None:
                column_names = [col for col in df_chart.columns if col != 'label']
                mapped_names = [variable_mapping.get(col, col) for col in column_names]
                fig = go.Figure(data=[go.Bar(x=mapped_names, y=row_data, name=label)])
                # Add annotations for zero values
                for i, value in enumerate(row_data):
                    if value == 0:
                        fig.add_annotation(x=mapped_names[i], y=value, text="0", showarrow=False, yshift=10)
                fig.update_layout(
                    title_text=f"Loan Distribution for {area_name}, {label}",
                    yaxis_title="Dollar Amount $(000's)",
                    xaxis_title="Loan Type"
                )
                figures.append(fig)
    else:
        row_data = df_chart.row(0)
        label = row_data[df_chart.columns.index('label')]
        row_data = list(row_data)
        row_data.pop(df_chart.columns.index('label'))
        column_names = [col for col in df_chart.columns if col != 'label']
        mapped_names = [variable_mapping.get(col, col) for col in column_names]
        fig = go.Figure(data=[go.Bar(x=mapped_names, y=row_data, name=area_name)])
        # Add annotations for zero values
        for i, value in enumerate(row_data):
            if value == 0:
                fig.add_annotation(x=mapped_names[i], y=value, text="0", showarrow=False, yshift=10)
        fig.update_layout(
            title_text=f"Loan Distribution for {area_name}, {label}",
            yaxis_title="Dollar Amount $(000's)",
            xaxis_title="Loan Type"
        )
        figures.append(fig)

    df_partial = df.filter(pl.col('Partial_Ind') == 'Y')
    total_loan_data = df_partial.sum().drop(['Partial_Ind', 'State_Code', 'County_Code', 'label'])

    total_loan_data = total_loan_data.with_columns([
        (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') +
         pl.col('Amt_Orig_MFam') + pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')).alias('Total Gross Loans')
    ])

    total_loan_data_list = [total_loan_data[col][0] for col in total_loan_data.columns]
    mapped_total_names = [variable_mapping.get(col, col) for col in total_loan_data.columns]
    fig = go.Figure(data=[go.Bar(x=mapped_total_names, y=total_loan_data_list, name="Total")])
    # Add annotations for zero values
    for i, value in enumerate(total_loan_data_list):
        if value == 0:
            fig.add_annotation(x=mapped_total_names[i], y=value, text="0", showarrow=False, yshift=10)
    fig.update_layout(
        title_text="Total Loan Distribution",
        yaxis_title="Dollar Amount $(000's)",
        xaxis_title="Loan Type"
    )
    figures.append(fig)

    return figures



def create_loan_distribution_chart(df, area_name, engine):
    def process_row(partial_ind, state_code, county_code):
            county_name = None
            for table in ['2024 tracts', '2022-2023 tracts']:
                query = f"SELECT `County name`, `State` FROM `{table}` WHERE `State code` = {state_code} AND `County code` = {county_code};"
                df_lookup = pl.read_database(query, engine)
                if df_lookup.height != 0:
                    county_name = df_lookup['County name'][0]
                    break
            if county_name is not None:
                return county_name
            return None

    df = df.with_columns([
        pl.struct(['Partial_Ind', 'State_Code', 'County_Code']).map_elements(lambda x: process_row(x['Partial_Ind'], x['State_Code'], x['County_Code'])).alias('label')
    ])

    df = df.with_columns([
        (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
         pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')).alias('Total Gross Loans')
    ])

    df_chart = df.drop(['Partial_Ind', 'State_Code', 'County_Code'])

    figures = []

    variable_mapping = {
        'Amt_Orig_SFam_Closed': '1-4 Family Closed-End',
        'Amt_Orig_SFam_Open': '1-4 Family Revolving',
        'Amt_Orig_MFam': 'Multi-Family',
        'SF_Amt_Orig': 'Farm Loans',
        'SB_Amt_Orig': 'Small Business Loans',
        'Amt_Orig': 'Total Mortgage Loan Amount',
        'Total Gross Loans': 'Total Gross Loans'
    }

    if df_chart.height > 1:
        print("I am > 1")
        for row in df_chart.iter_rows():
            row_data = list(row)
            label = row_data[df_chart.columns.index('label')]
            row_data.pop(df_chart.columns.index('label'))
            if label is not None:
                column_names = [col for col in df_chart.columns if col != 'label']
                mapped_names = [variable_mapping.get(col, col) for col in column_names]
                fig = go.Figure(data=[go.Bar(x=mapped_names, y=row_data, name=label)])
                # Add annotations for zero values
                for i, value in enumerate(row_data):
                    if value == 0:
                        fig.add_annotation(x=mapped_names[i], y=value, text="0", showarrow=False, yshift=10)
                fig.update_layout(
                    title_text=f"Loan Distribution for {area_name}, {label}",
                    yaxis_title="Dollar Amount $(000's)",
                    xaxis_title="Loan Type"
                )
                figures.append(fig)
    else:
        print("I am 1")
        row_data = df_chart.row(0)  # Correctly fetch the single row
        label = row_data[df_chart.columns.index('label')]  # Extract the label
        print(f"Label: {label}")  # Debugging: print the extracted label
        row_data = list(row_data)  # Convert row data to a list for processing
        row_data.pop(df_chart.columns.index('label'))  # Remove label from row data
        column_names = [col for col in df_chart.columns if col != 'label']  # Get column names excluding 'label'
        mapped_names = [variable_mapping.get(col, col) for col in column_names]  # Map column names using variable_mapping
        fig = go.Figure(data=[go.Bar(x=mapped_names, y=row_data, name=label)])  # Create the figure using the label

        # Add annotations for zero values
        for i, value in enumerate(row_data):
            if value == 0:
                fig.add_annotation(x=mapped_names[i], y=value, text="0", showarrow=False, yshift=10)

        # Set figure layout
        fig.update_layout(
            title_text=f"Loan Distribution for {area_name}, {label}",
            yaxis_title="Dollar Amount $(000's)",
            xaxis_title="Loan Type"
        )
        figures.append(fig)  # Append the figure to the list of figures

    df_partial = df.filter(pl.col('Partial_Ind') == 'Y')

    # Add condition to check if df_partial is not empty
    if df_partial.height > 0:
        total_loan_data = df_partial.sum().drop(['Partial_Ind', 'State_Code', 'County_Code', 'label'])

        total_loan_data = total_loan_data.with_columns([
            (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') +
            pl.col('Amt_Orig_MFam') + pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')).alias('Total Gross Loans')
        ])

        total_loan_data_list = [total_loan_data[col][0] for col in total_loan_data.columns]
        mapped_total_names = [variable_mapping.get(col, col) for col in total_loan_data.columns]
        fig = go.Figure(data=[go.Bar(x=mapped_total_names, y=total_loan_data_list, name="Total")])
        # Add annotations for zero values
        for i, value in enumerate(total_loan_data_list):
            if value == 0:
                fig.add_annotation(x=mapped_total_names[i], y=value, text="0", showarrow=False, yshift=10)
        fig.update_layout(
            title_text="Total Loan Distribution",
            yaxis_title="Dollar Amount $(000's)",
            xaxis_title="Loan Type"
        )
        figures.append(fig)

    return figures




def create_loan_distribution_great_tables(df, area_name, engine):
    def process_row(state_code, county_code):
        county_name = None
        for table in ['2024 tracts', '2022-2023 tracts']:
                query = f"SELECT `County name`, `State` FROM `{table}` WHERE `State code` = {state_code} AND `County code` = {county_code};"
                df_lookup = pl.read_database(query, engine)
                if len(df_lookup) != 0:
                    county_name = df_lookup['County name'][0]
                    break
        if county_name is not None:
                label = f"{county_name}"
                return label
        return None

    # Process loan data if needed
    df = df.with_columns([
        pl.struct(['State_Code', 'County_Code']).map_elements(lambda x: process_row(x['State_Code'], x['County_Code'])).alias('label')
    ])

    df = df.with_columns([
        (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
     pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig') - pl.col('Amt_Orig')).alias('Other Loans'),
    (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
     pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')).alias('Total Gross Loans')

])  
    
    if len(df) > 1:
        totals = {
            'Amt_Orig_SFam_Closed': df['Amt_Orig_SFam_Closed'].sum(),
            'Amt_Orig_SFam_Open': df['Amt_Orig_SFam_Open'].sum(),
            'Amt_Orig_MFam': df['Amt_Orig_MFam'].sum(),
            'SF_Amt_Orig': df['SF_Amt_Orig'].sum(),
            'SB_Amt_Orig': df['SB_Amt_Orig'].sum(),
            'Amt_Orig': df['Amt_Orig'].sum(), 
            'Partial_Ind': None,
            'State_Code': None,
            'County_Code': None,
            'label': 'Overall',
            'Other Loans': df['Other Loans'].sum(),
            'Total Gross Loans': df['Total Gross Loans'].sum()
        }
        df_totals = pl.DataFrame([totals])
        df = df.vstack(df_totals)

    # Ensure columns are correctly typed (if necessary)
    df = df.cast(
        {'Amt_Orig_SFam_Closed': pl.Int64,
         'Amt_Orig_SFam_Open': pl.Int64,
         'Amt_Orig_MFam': pl.Int64,
         'SF_Amt_Orig': pl.Int64,
         'SB_Amt_Orig': pl.Int64,
         'Amt_Orig': pl.Int64,
         'Other Loans': pl.Int64,
         'Total Gross Loans': pl.Int64}
    )

    df = df.rename(
    {
        'Amt_Orig_SFam_Closed': '1-4 Family Closed-End',
        'Amt_Orig_SFam_Open': '1-4 Family Revolving',
        'Amt_Orig_MFam': 'Multi-Family',
        'SF_Amt_Orig': 'Farm Loans',
        'SB_Amt_Orig': 'Small Business Loans',
        'Amt_Orig': 'Total Mortgage Amount',
        'label': 'County'
    }
)

    # Create Great Tables instance with Polars DataFrame
    gt_instance = (
    GT(df)
    .opt_table_outline()
    .opt_stylize(style = 2, color = "blue")
    .tab_header("Loan Distribution (in 000's)")
    .tab_spanner(label="Loan Type", columns=['1-4 Family Closed-End', '1-4 Family Revolving', 'Multi-Family', 'Small Business Loans', 'Farm Loans'])
    .tab_spanner(label="Totals (in 000's)", columns=['Total Mortgage Amount', 'Other Loans', 'Total Gross Loans'])
    .cols_hide(columns=['Partial_Ind', 'State_Code', 'County_Code'])
    .fmt_number(columns=['1-4 Family Closed-End', '1-4 Family Revolving', 'Multi-Family', 'Small Business Loans', 'Farm Loans', 'Total Mortgage Amount', 'Total Gross Loans', 'Other Loans'], decimals=0, use_seps=True)  
    .tab_stubhead(label = "County")
    .tab_stub(rowname_col="County")
    .tab_options(
    table_body_hlines_style="solid",
    table_body_vlines_style="solid",
    table_body_border_top_color="gray",
    table_body_border_bottom_color="gray",
    container_width = "100%"   
    )
    )

    # Return Great Tables instance
    return gt_instance


def create_loan_distribution_percentage_tables(df, area_name, engine):
    def process_row(state_code, county_code):
        county_name = None
        for table in ['2024 tracts', '2022-2023 tracts']:
                query = f"SELECT `County name`, `State` FROM `{table}` WHERE `State code` = {state_code} AND `County code` = {county_code};"
                df_lookup = pl.read_database(query, engine)
                if len(df_lookup) != 0:
                    county_name = df_lookup['County name'][0]
                    break
        if county_name is not None:
                label = f"{county_name}"
                return label
        return None

    # Process loan data if needed
    df = df.with_columns([
        pl.struct(['State_Code', 'County_Code']).map_elements(lambda x: process_row(x['State_Code'], x['County_Code'])).alias('label')
    ])

    df = df.with_columns([
        (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
     pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig') - pl.col('Amt_Orig')).alias('Other Loans'),
    (pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
     pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')).alias('Total Gross Loans')])

    df = df.with_columns([
    ((pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
     pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig') - pl.col('Amt_Orig')) / pl.col('Total Gross Loans')).alias('Other Loans %'),
    ((pl.col('Amt_Orig_SFam_Closed') + pl.col('Amt_Orig_SFam_Open') + pl.col('Amt_Orig_MFam') + 
     pl.col('SF_Amt_Orig') + pl.col('SB_Amt_Orig')) / pl.col('Total Gross Loans')).alias('Total Gross Loan %')
    ])  

    if len(df) > 1:
        totals = {
            'Amt_Orig_SFam_Closed': df['Amt_Orig_SFam_Closed'].sum(),
            'Amt_Orig_SFam_Open': df['Amt_Orig_SFam_Open'].sum(),
            'Amt_Orig_MFam': df['Amt_Orig_MFam'].sum(),
            'SF_Amt_Orig': df['SF_Amt_Orig'].sum(),
            'SB_Amt_Orig': df['SB_Amt_Orig'].sum(),
            'Amt_Orig': df['Amt_Orig'].sum(), 
            'Partial_Ind': None,
            'State_Code': None,
            'County_Code': None,
            'label': 'Overall',
            'Other Loans': df['Other Loans'].sum(),
            'Total Gross Loans': df['Total Gross Loans'].sum(),
        }
        totals['Other Loans %'] = totals['Other Loans'] / totals['Total Gross Loans']
        totals['Total Gross Loan %'] = (totals['Amt_Orig_SFam_Closed'] + totals['Amt_Orig_SFam_Open'] + totals['Amt_Orig_MFam'] + totals['SF_Amt_Orig'] + totals['SB_Amt_Orig']) / totals['Total Gross Loans']
        df_totals = pl.DataFrame([totals])
        df = df.vstack(df_totals)

    # Ensure columns are correctly typed (if necessary)
    df = df.cast(
        {'Amt_Orig_SFam_Closed': pl.Float64,
         'Amt_Orig_SFam_Open': pl.Float64,
         'Amt_Orig_MFam': pl.Float64,
         'SF_Amt_Orig': pl.Float64,
         'SB_Amt_Orig': pl.Float64,
         'Amt_Orig': pl.Float64,
         'Other Loans': pl.Float64,
         'Total Gross Loans': pl.Float64,
         'Other Loans %': pl.Float64,
         'Total Gross Loan %': pl.Float64}
    )

    df = df.with_columns([
    (pl.col('Amt_Orig_SFam_Closed') / pl.col('Total Gross Loans')).alias('1-4 Family Closed-End %'),
    (pl.col('Amt_Orig_SFam_Open') / pl.col('Total Gross Loans')).alias('1-4 Family Revolving %'),
    (pl.col('Amt_Orig_MFam') / pl.col('Total Gross Loans')).alias('Multi-Family %'),
    (pl.col('SF_Amt_Orig') / pl.col('Total Gross Loans')).alias('Farm Loans %'),
    (pl.col('SB_Amt_Orig') / pl.col('Total Gross Loans')).alias('Small Business Loans %'),
    (pl.col('Amt_Orig') / pl.col('Total Gross Loans')).alias('Total Mortgage %'),
])

    
    df = df.rename(
{
    '1-4 Family Closed-End %': '1-4 Family Closed-End',
    '1-4 Family Revolving %': '1-4 Family Revolving',
    'Multi-Family %': 'Multi-Family',
    'Farm Loans %': 'Farm Loans',
    'Small Business Loans %': 'Small Business Loans',
    'label': 'County'
})

    # Create Great Tables instance with Polars DataFrame
    gt_instance = (
    GT(df)
    .opt_table_outline()
    .opt_stylize(style = 2, color = "blue")
    .tab_header("Loan Distribution (in %)")
    .tab_spanner(label="Loan Type", columns=['1-4 Family Closed-End', '1-4 Family Revolving', 'Multi-Family', 'Small Business Loans', 'Farm Loans'])
    .tab_spanner(label="Totals (in %)", columns=['Total Mortgage %', 'Other Loans %', 'Total Gross Loan %'])
    .cols_hide(columns=['Partial_Ind', 'State_Code', 'County_Code', 'Total Gross Loans', 'Other Loans', 'Amt_Orig_SFam_Closed', 'SF_Amt_Orig', 'SB_Amt_Orig', 'Amt_Orig', 'Amt_Orig_SFam_Open', 'Amt_Orig_MFam'])
    .fmt_percent(columns=['1-4 Family Closed-End', '1-4 Family Revolving', 'Multi-Family', 'Small Business Loans', 'Farm Loans', 'Total Mortgage %', 'Other Loans %', 'Total Gross Loan %'], decimals=1)  
    .tab_stubhead(label = "County")
    .tab_stub(rowname_col="County")
    .tab_options(
    table_body_hlines_style="solid",
    table_body_vlines_style="solid",
    table_body_border_top_color="gray",
    table_body_border_bottom_color="gray",
    container_width = "100%"   
    )
    )

    # Return Great Tables instance
    return gt_instance
