#!/usr/bin/env python3
"""
Script to convert Folha_IA.xlsx data to JSON files for frontend consumption.
Includes OEE (Overall Equipment Effectiveness) calculations.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

# Paths
EXCEL_PATH = Path(__file__).parent.parent / "Folha_IA.xlsx"
OUTPUT_DIR = Path(__file__).parent.parent / "frontend" / "src" / "data"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat() if pd.notna(obj) else None
    if pd.isna(obj):
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not serializable")


def save_json(data, filename):
    """Save data to JSON file"""
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_serial)
    record_count = len(data) if isinstance(data, list) else 'object'
    print(f"✓ Saved {filename} ({record_count} records)")


def get_kayak_type(name):
    """Extract kayak type from product name"""
    if pd.isna(name):
        return 'Other'
    name = str(name)
    for prefix in ['K1', 'K2', 'K4', 'C1', 'C2', 'C4']:
        if name.startswith(prefix):
            return prefix
    return 'Other'


def convert_products(xlsx):
    """Convert Modelos sheet to products.json"""
    df = pd.read_excel(xlsx, sheet_name='Modelos')
    
    products = []
    for _, row in df.iterrows():
        name = str(row['Produto_Nome'])
        product_type = get_kayak_type(name)
        
        products.append({
            'id': str(int(row['Produto_Id'])),
            'name': name,
            'type': product_type,
            'weightDismold': float(row['Produto_PesoDesmolde']) if pd.notna(row['Produto_PesoDesmolde']) else 0,
            'weightFinish': float(row['Produto_PesoAcabamento']) if pd.notna(row['Produto_PesoAcabamento']) else 0,
            'gelDeck': float(row['Produto_QtdGelDeck']) if pd.notna(row['Produto_QtdGelDeck']) else 0,
            'gelHull': float(row['Produto_QtdGelCasco']) if pd.notna(row['Produto_QtdGelCasco']) else 0,
            'status': 'ACTIVE'
        })
    
    save_json(products, 'products.json')
    return products


def convert_phases(xlsx):
    """Convert Fases sheet to phases.json"""
    df = pd.read_excel(xlsx, sheet_name='Fases')
    
    phases = []
    for _, row in df.iterrows():
        phases.append({
            'id': str(int(row['Fase_Id'])),
            'name': row['Fase_Nome'],
            'sequence': int(row['Fase_Sequencia']) if pd.notna(row['Fase_Sequencia']) else 0,
            'isProduction': bool(row['Fase_DeProducao']),
            'isAutomatic': bool(row['Fase_Automatica']),
            'status': 'ACTIVE'
        })
    
    save_json(phases, 'phases.json')
    return phases


def convert_employees(xlsx):
    """Convert Funcionarios and FuncionariosFasesAptos to employees.json"""
    df_employees = pd.read_excel(xlsx, sheet_name='Funcionarios')
    df_skills = pd.read_excel(xlsx, sheet_name='FuncionariosFasesAptos')
    df_phases = pd.read_excel(xlsx, sheet_name='Fases')
    
    phase_names = dict(zip(df_phases['Fase_Id'], df_phases['Fase_Nome']))
    skills_by_employee = df_skills.groupby('FuncionarioFase_FuncionarioId')['FuncionarioFase_FaseId'].apply(list).to_dict()
    df_employees = df_employees.drop_duplicates(subset=['Funcionario_Id'])
    
    employees = []
    for _, row in df_employees.iterrows():
        emp_id = row['Funcionario_Id']
        name = str(row['Funcionario_Nome']).strip()
        
        if name.startswith('z)'):
            continue
            
        skill_ids = skills_by_employee.get(emp_id, [])
        skill_names = [phase_names.get(sid, f'Phase {sid}') for sid in skill_ids]
        
        employees.append({
            'id': str(int(emp_id)),
            'name': name,
            'status': 'ACTIVE' if row['Funcionario_Activo'] == 1 else 'INACTIVE',
            'skills': skill_names[:5],
            'skillIds': [str(int(s)) for s in skill_ids[:5]],
            'department': skill_names[0] if skill_names else 'General'
        })
    
    save_json(employees, 'employees.json')
    return employees


def convert_orders(xlsx, products_lookup):
    """Convert OrdensFabrico to orders.json"""
    df = pd.read_excel(xlsx, sheet_name='OrdensFabrico')
    df_phases = pd.read_excel(xlsx, sheet_name='Fases')
    
    phase_names = dict(zip(df_phases['Fase_Id'], df_phases['Fase_Nome']))
    product_names = {p['id']: p['name'] for p in products_lookup}
    
    df = df.sort_values('Of_DataCriacao', ascending=False)
    df_sample = df.head(200)
    
    orders = []
    for _, row in df_sample.iterrows():
        order_id = row['Of_Id']
        product_id = str(int(row['Of_ProdutoId'])) if pd.notna(row['Of_ProdutoId']) else None
        current_phase = row['Of_FaseId']
        
        status = 'IN_PROGRESS' if pd.isna(row['Of_DataAcabamento']) else 'COMPLETED'
        
        orders.append({
            'id': str(int(order_id)),
            'productId': product_id,
            'productName': product_names.get(product_id, f'Product {product_id}') if product_id else 'Unknown',
            'createdDate': row['Of_DataCriacao'].isoformat() if pd.notna(row['Of_DataCriacao']) else None,
            'completedDate': row['Of_DataAcabamento'].isoformat() if pd.notna(row['Of_DataAcabamento']) else None,
            'transportDate': row['Of_DataTransporte'].isoformat() if pd.notna(row['Of_DataTransporte']) else None,
            'currentPhaseId': str(int(current_phase)) if pd.notna(current_phase) else None,
            'currentPhaseName': phase_names.get(current_phase, 'Unknown'),
            'status': status
        })
    
    save_json(orders, 'orders.json')
    return orders


def convert_errors(xlsx):
    """Convert OrdemFabricoErros to errors.json"""
    df = pd.read_excel(xlsx, sheet_name='OrdemFabricoErros')
    df_phases = pd.read_excel(xlsx, sheet_name='Fases')
    
    phase_names = dict(zip(df_phases['Fase_Id'], df_phases['Fase_Nome']))
    df_sample = df.head(500)
    
    errors = []
    for _, row in df_sample.iterrows():
        phase_id = row['Erro_FaseAvaliacao']
        
        errors.append({
            'id': str(len(errors) + 1),
            'description': row['Erro_Descricao'],
            'orderId': str(int(row['Erro_OfId'])),
            'phaseId': str(int(phase_id)) if pd.notna(phase_id) else None,
            'phaseName': phase_names.get(phase_id, 'Unknown'),
            'severity': int(row['OFCH_GRAVIDADE']) if pd.notna(row['OFCH_GRAVIDADE']) else 1,
            'evaluationPhaseId': str(int(row['Erro_FaseOfAvaliacao'])) if pd.notna(row['Erro_FaseOfAvaliacao']) else None,
            'culpablePhaseId': str(int(row['Erro_FaseOfCulpada'])) if pd.notna(row['Erro_FaseOfCulpada']) else None
        })
    
    save_json(errors, 'errors.json')
    return errors


def convert_standard_times(xlsx, products_lookup, phases_lookup):
    """Convert FasesStandardModelos to standardTimes.json with correct names"""
    df = pd.read_excel(xlsx, sheet_name='FasesStandardModelos')
    
    # Create lookups with integer keys
    product_names = {p['id']: p['name'] for p in products_lookup}
    phase_names = {p['id']: p['name'] for p in phases_lookup}
    
    standard_times = []
    for _, row in df.iterrows():
        product_id = str(int(row['ProdutoFase_ProdutoId']))
        phase_id = str(int(row['ProdutoFase_FaseId']))
        
        standard_times.append({
            'productId': product_id,
            'productName': product_names.get(product_id, f'Product {product_id}'),
            'phaseId': phase_id,
            'phaseName': phase_names.get(phase_id, f'Phase {phase_id}'),
            'sequence': int(row['ProdutoFase_Sequencia']) if pd.notna(row['ProdutoFase_Sequencia']) else 0,
            'coefficient': float(row['ProdutoFase_Coeficiente']) if pd.notna(row['ProdutoFase_Coeficiente']) else 0,
            'coefficientX': float(row['ProdutoFase_CoeficienteX']) if pd.notna(row['ProdutoFase_CoeficienteX']) else 0
        })
    
    save_json(standard_times, 'standardTimes.json')
    return standard_times


def convert_allocations(xlsx, employees_lookup):
    """Convert FuncionariosFaseOrdemFabrico to allocations.json
    
    Also generates allocationStats.json with REAL totals from full Excel data.
    """
    df = pd.read_excel(xlsx, sheet_name='FuncionariosFaseOrdemFabrico')
    df_phases_of = pd.read_excel(xlsx, sheet_name='FasesOrdemFabrico')
    df_phases = pd.read_excel(xlsx, sheet_name='Fases')
    
    employee_names = {e['id']: e['name'] for e in employees_lookup}
    phase_names = dict(zip(df_phases['Fase_Id'], df_phases['Fase_Nome']))
    phase_of_info = df_phases_of.set_index('FaseOf_Id')[['FaseOf_FaseId', 'FaseOf_Inicio', 'FaseOf_Fim']].to_dict('index')
    
    # Calculate REAL stats from FULL Excel data (before sampling)
    total_allocations = len(df)
    leader_allocations = len(df[df['FuncionarioFaseOf_Chefe'] == True])
    unique_employees_in_allocations = df['FuncionarioFaseOf_FuncionarioId'].nunique()
    
    # Merge with phase info to get start times for sorting
    df_merged = df.merge(
        df_phases_of[['FaseOf_Id', 'FaseOf_Inicio']], 
        left_on='FuncionarioFaseOf_FaseOfId', 
        right_on='FaseOf_Id', 
        how='left'
    )
    
    # Sort by start time DESC (most recent first) and take top 500
    df_sorted = df_merged.sort_values('FaseOf_Inicio', ascending=False, na_position='last')
    df_sample = df_sorted.head(500)
    
    allocations = []
    for _, row in df_sample.iterrows():
        phase_of_id = row['FuncionarioFaseOf_FaseOfId']
        employee_id = str(int(row['FuncionarioFaseOf_FuncionarioId']))
        
        phase_info = phase_of_info.get(phase_of_id, {})
        phase_id = phase_info.get('FaseOf_FaseId')
        
        allocations.append({
            'id': str(len(allocations) + 1),
            'employeeId': employee_id,
            'employeeName': employee_names.get(employee_id, f'Employee {employee_id}'),
            'phaseOrderId': str(int(phase_of_id)),
            'phaseId': str(int(phase_id)) if pd.notna(phase_id) else None,
            'phaseName': phase_names.get(phase_id, 'Unknown'),
            'isLeader': bool(row['FuncionarioFaseOf_Chefe']),
            'startTime': phase_info.get('FaseOf_Inicio').isoformat() if pd.notna(phase_info.get('FaseOf_Inicio')) else None,
            'endTime': phase_info.get('FaseOf_Fim').isoformat() if pd.notna(phase_info.get('FaseOf_Fim')) else None
        })
    
    save_json(allocations, 'allocations.json')
    
    # Save REAL allocation stats (from FULL data, not sample)
    allocation_stats = {
        'totalAllocations': int(total_allocations),
        'leaderAllocations': int(leader_allocations),
        'uniqueEmployees': int(unique_employees_in_allocations),
        'sampleSize': len(allocations),
        'sampleDescription': 'Most recent 500 allocations sorted by start time DESC'
    }
    save_json(allocation_stats, 'allocationStats.json')
    print(f"  Total Allocations (real): {total_allocations:,}")
    print(f"  Leader Allocations (real): {leader_allocations:,}")
    
    return allocations


def calculate_oee_metrics(xlsx):
    """Calculate OEE (Overall Equipment Effectiveness) metrics"""
    print("\n=== Calculating OEE Metrics ===\n")
    
    df_orders = pd.read_excel(xlsx, sheet_name='OrdensFabrico')
    df_phases_of = pd.read_excel(xlsx, sheet_name='FasesOrdemFabrico')
    df_errors = pd.read_excel(xlsx, sheet_name='OrdemFabricoErros')
    df_phases = pd.read_excel(xlsx, sheet_name='Fases')
    df_products = pd.read_excel(xlsx, sheet_name='Modelos')
    
    phase_names = dict(zip(df_phases['Fase_Id'], df_phases['Fase_Nome']))
    
    # Calculate orders in progress and completed from FULL Excel data
    orders_in_progress = len(df_orders[df_orders['Of_DataAcabamento'].isna()])
    orders_completed = len(df_orders[df_orders['Of_DataAcabamento'].notna()])
    
    # 1. QUALITY DIMENSION (FPY - First Pass Yield)
    orders_with_errors = set(df_errors['Erro_OfId'].unique())
    total_orders = len(df_orders)
    orders_fpy = total_orders - len(orders_with_errors)
    quality_rate = orders_fpy / total_orders if total_orders > 0 else 0
    
    # 2. PERFORMANCE DIMENSION (actual vs standard time)
    df_phases_of['actual_duration'] = (
        pd.to_datetime(df_phases_of['FaseOf_Fim']) - 
        pd.to_datetime(df_phases_of['FaseOf_Inicio'])
    ).dt.total_seconds() / 3600
    
    valid_phases = df_phases_of[
        (df_phases_of['actual_duration'] > 0) & 
        (df_phases_of['actual_duration'] < 24)
    ]
    
    valid_with_std = valid_phases[valid_phases['FaseOf_Coeficiente'] > 0]
    avg_std = valid_with_std['FaseOf_Coeficiente'].mean() if len(valid_with_std) > 0 else 0
    avg_actual = valid_with_std['actual_duration'].mean() if len(valid_with_std) > 0 else 1
    performance_rate = min(avg_std / avg_actual, 1.0) if avg_actual > 0 else 0
    
    # 3. AVAILABILITY DIMENSION (phases started)
    phases_started = df_phases_of[pd.to_datetime(df_phases_of['FaseOf_Inicio']).dt.year > 1901]
    availability_rate = len(phases_started) / len(df_phases_of) if len(df_phases_of) > 0 else 0
    
    # 4. OEE CALCULATION
    oee = availability_rate * performance_rate * quality_rate
    
    # 5. FPY BY PRODUCT FAMILY
    df_products['kayak_type'] = df_products['Produto_Nome'].apply(get_kayak_type)
    product_types = dict(zip(df_products['Produto_Id'], df_products['kayak_type']))
    df_orders['kayak_type'] = df_orders['Of_ProdutoId'].map(product_types).fillna('Other')
    
    fpy_by_family = {}
    for kayak_type in ['K1', 'K2', 'K4', 'C1', 'C2', 'Other']:
        type_orders = df_orders[df_orders['kayak_type'] == kayak_type]
        if len(type_orders) > 0:
            type_with_errors = len(type_orders[type_orders['Of_Id'].isin(orders_with_errors)])
            type_fpy = (len(type_orders) - type_with_errors) / len(type_orders)
            fpy_by_family[kayak_type] = {
                'totalOrders': len(type_orders),
                'ordersWithErrors': int(type_with_errors),
                'fpy': round(type_fpy * 100, 1)
            }
    
    # 6. PERFORMANCE BY PHASE
    performance_by_phase = []
    for phase_id in valid_with_std['FaseOf_FaseId'].unique():
        phase_data = valid_with_std[valid_with_std['FaseOf_FaseId'] == phase_id]
        if len(phase_data) > 0:
            phase_avg_std = phase_data['FaseOf_Coeficiente'].mean()
            phase_avg_actual = phase_data['actual_duration'].mean()
            phase_performance = min(phase_avg_std / phase_avg_actual, 1.0) if phase_avg_actual > 0 else 0
            performance_by_phase.append({
                'phaseId': str(int(phase_id)),
                'phaseName': phase_names.get(phase_id, f'Phase {phase_id}'),
                'avgStandardTime': round(phase_avg_std, 2),
                'avgActualTime': round(phase_avg_actual, 2),
                'performance': round(phase_performance * 100, 1),
                'recordCount': len(phase_data)
            })
    
    performance_by_phase.sort(key=lambda x: x['recordCount'], reverse=True)
    
    oee_metrics = {
        'oee': round(oee * 100, 1),
        'availability': round(availability_rate * 100, 1),
        'performance': round(performance_rate * 100, 1),
        'quality': round(quality_rate * 100, 1),
        'totalOrders': int(total_orders),
        'ordersInProgress': int(orders_in_progress),
        'ordersCompleted': int(orders_completed),
        'ordersWithErrors': len(orders_with_errors),
        'ordersWithoutErrors': int(orders_fpy),
        'reworkRate': round((1 - quality_rate) * 100, 1),
        'avgStandardTime': round(avg_std, 2),
        'avgActualTime': round(avg_actual, 2),
        'phasesStarted': len(phases_started),
        'totalPhases': len(df_phases_of),
        'fpyByFamily': fpy_by_family,
        'performanceByPhase': performance_by_phase[:15],  # Top 15 phases
        # Flags to indicate which metrics are estimates vs real data
        'isEstimate': {
            'oee': True,  # Calculated from availability x performance x quality
            'availability': True,  # Estimated as phases_started / total_phases
            'performance': True,  # Estimated as avg_std_time / avg_actual_time
            'quality': False,  # REAL - based on actual error records
            'reworkRate': False  # REAL - based on actual error records
        },
        'methodology': {
            'availability': 'Fases iniciadas / Total de fases',
            'performance': 'Tempo padrão médio / Tempo real médio (limitado a 100%)',
            'quality': 'Ordens sem erros / Total de ordens (FPY)',
            'oee': 'Disponibilidade x Desempenho x Qualidade'
        }
    }
    
    save_json(oee_metrics, 'oeeMetrics.json')
    print(f"  OEE: {oee_metrics['oee']}%")
    print(f"  Availability: {oee_metrics['availability']}%")
    print(f"  Performance: {oee_metrics['performance']}%")
    print(f"  Quality (FPY): {oee_metrics['quality']}%")
    
    return oee_metrics


def calculate_quality_analysis(xlsx):
    """Calculate detailed quality analysis"""
    print("\n=== Calculating Quality Analysis ===\n")
    
    df_errors = pd.read_excel(xlsx, sheet_name='OrdemFabricoErros')
    df_phases = pd.read_excel(xlsx, sheet_name='Fases')
    
    phase_names = dict(zip(df_phases['Fase_Id'], df_phases['Fase_Nome']))
    
    # 1. TOP ERRORS BY DESCRIPTION
    error_counts = df_errors['Erro_Descricao'].value_counts().head(20)
    top_errors = [
        {'description': desc, 'count': int(count), 'percentage': round(count / len(df_errors) * 100, 1)}
        for desc, count in error_counts.items()
    ]
    
    # 2. ERRORS BY SEVERITY
    severity_counts = df_errors.groupby('OFCH_GRAVIDADE').size()
    errors_by_severity = [
        {
            'severity': int(sev),
            'severityLabel': ['Minor', 'Major', 'Critical'][int(sev) - 1] if 1 <= sev <= 3 else 'Unknown',
            'count': int(count),
            'percentage': round(count / len(df_errors) * 100, 1)
        }
        for sev, count in severity_counts.items()
    ]
    
    # 3. ERRORS BY EVALUATION PHASE
    errors_by_eval_phase = df_errors.groupby('Erro_FaseAvaliacao').size().sort_values(ascending=False)
    errors_by_phase = [
        {
            'phaseId': str(int(phase_id)),
            'phaseName': phase_names.get(phase_id, f'Phase {phase_id}'),
            'count': int(count),
            'percentage': round(count / len(df_errors) * 100, 1)
        }
        for phase_id, count in errors_by_eval_phase.head(10).items()
    ]
    
    # 4. ERROR CATEGORIES (grouping similar errors)
    error_categories = {
        'Molde': ['Molde baço', 'Molde com deformações/danos', 'Molde com lixo'],
        'Laminagem': ['Laminagem com bolhas', 'Laminagem contraído', 'Laminagem deslaminado', 'Interior enrugado', 'Interior esbranquiçado'],
        'Pintura': ['Pintura transparente', 'Pintura com linhas tortas', 'Pintura com fios', 'Pintura com lixo', 'Pintura Malhada', 'Pintura com escorridos'],
    }
    
    category_counts = []
    for category, keywords in error_categories.items():
        count = sum(df_errors['Erro_Descricao'].str.contains('|'.join(keywords), case=False, na=False))
        category_counts.append({
            'category': category,
            'count': int(count),
            'percentage': round(count / len(df_errors) * 100, 1)
        })
    
    # Add "Other" category
    categorized = sum(c['count'] for c in category_counts)
    category_counts.append({
        'category': 'Other',
        'count': int(len(df_errors) - categorized),
        'percentage': round((len(df_errors) - categorized) / len(df_errors) * 100, 1)
    })
    
    quality_analysis = {
        'totalErrors': len(df_errors),
        'topErrors': top_errors,
        'errorsBySeverity': errors_by_severity,
        'errorsByPhase': errors_by_phase,
        'errorsByCategory': category_counts,
        'criticalErrorsCount': int(severity_counts.get(3, 0)),
        'majorErrorsCount': int(severity_counts.get(2, 0)),
        'minorErrorsCount': int(severity_counts.get(1, 0))
    }
    
    save_json(quality_analysis, 'qualityAnalysis.json')
    print(f"  Total Errors: {quality_analysis['totalErrors']}")
    print(f"  Critical: {quality_analysis['criticalErrorsCount']}")
    print(f"  Major: {quality_analysis['majorErrorsCount']}")
    print(f"  Minor: {quality_analysis['minorErrorsCount']}")
    
    return quality_analysis


def generate_dashboard_stats(products, employees, orders, errors, oee_metrics, quality_analysis):
    """Generate aggregated stats for dashboard including OEE
    
    NOTE: Orders and Errors counts use FULL Excel data from oee_metrics/quality_analysis,
    NOT from sampled orders/errors lists (which are only for UI listings).
    """
    active_employees = len([e for e in employees if e['status'] == 'ACTIVE'])
    
    # Product types distribution (complete data)
    product_types = {}
    for p in products:
        pt = p['type']
        product_types[pt] = product_types.get(pt, 0) + 1
    
    # Error severity from quality_analysis (FULL Excel data)
    error_by_severity = {
        1: quality_analysis['minorErrorsCount'],
        2: quality_analysis['majorErrorsCount'],
        3: quality_analysis['criticalErrorsCount']
    }
    
    stats = {
        # Products and Employees - complete data from JSON
        'totalProducts': len(products),
        'activeEmployees': active_employees,
        'totalEmployees': len(employees),
        'productsByType': product_types,
        
        # Orders - from oee_metrics (FULL Excel data, not sampled)
        'ordersInProgress': oee_metrics['ordersInProgress'],
        'ordersCompleted': oee_metrics['ordersCompleted'],
        'totalOrders': oee_metrics['totalOrders'],
        
        # Errors - from quality_analysis (FULL Excel data, not sampled)
        'totalErrors': quality_analysis['totalErrors'],
        'errorsBySeverity': error_by_severity,
        'criticalErrors': quality_analysis['criticalErrorsCount'],
        'majorErrors': quality_analysis['majorErrorsCount'],
        'minorErrors': quality_analysis['minorErrorsCount'],
        
        # OEE Metrics
        'oee': oee_metrics['oee'],
        'availability': oee_metrics['availability'],
        'performance': oee_metrics['performance'],
        'quality': oee_metrics['quality'],
        'fpy': oee_metrics['quality'],
        'reworkRate': oee_metrics['reworkRate']
    }
    
    save_json(stats, 'dashboardStats.json')
    return stats


def validate_invariants(oee_metrics, quality_analysis, standard_times):
    """Validate data invariants to ensure consistency"""
    print("\n=== Validating Invariants ===\n")
    
    errors = []
    
    # 1. Orders: total = in_progress + completed
    total = oee_metrics['totalOrders']
    in_progress = oee_metrics['ordersInProgress']
    completed = oee_metrics['ordersCompleted']
    if total != in_progress + completed:
        errors.append(f"FAILED: totalOrders ({total}) != inProgress ({in_progress}) + completed ({completed})")
    else:
        print(f"✓ totalOrders ({total:,}) = inProgress ({in_progress:,}) + completed ({completed:,})")
    
    # 2. FPY + reworkRate = 100%
    fpy = oee_metrics['quality']
    rework = oee_metrics['reworkRate']
    if abs(fpy + rework - 100) > 0.1:
        errors.append(f"FAILED: FPY ({fpy}%) + reworkRate ({rework}%) != 100%")
    else:
        print(f"✓ FPY ({fpy}%) + reworkRate ({rework}%) = 100%")
    
    # 3. Standard times: labor + machine = total
    labor_total = sum(st['coefficient'] for st in standard_times)
    machine_total = sum(st['coefficientX'] for st in standard_times)
    total_hours = labor_total + machine_total
    labor_ratio = labor_total / total_hours * 100 if total_hours > 0 else 0
    print(f"✓ Standard Times: labor={labor_total:.0f}h + machine={machine_total:.0f}h = {total_hours:.0f}h (labor ratio: {labor_ratio:.1f}%)")
    
    # 4. Error severity counts match total
    minor = quality_analysis['minorErrorsCount']
    major = quality_analysis['majorErrorsCount']
    critical = quality_analysis['criticalErrorsCount']
    total_errors = quality_analysis['totalErrors']
    severity_sum = minor + major + critical
    if severity_sum != total_errors:
        print(f"⚠ Severity sum ({severity_sum:,}) != totalErrors ({total_errors:,}) - some errors may have NULL severity")
    else:
        print(f"✓ Error severity: minor ({minor:,}) + major ({major:,}) + critical ({critical:,}) = {total_errors:,}")
    
    if errors:
        print("\n⚠️ VALIDATION FAILED:")
        for err in errors:
            print(f"  {err}")
        return False
    
    print("\n✅ All invariants validated successfully")
    return True


def main():
    print(f"Reading Excel file: {EXCEL_PATH}")
    xlsx = pd.ExcelFile(EXCEL_PATH)
    
    print("\n=== Converting sheets to JSON ===\n")
    
    products = convert_products(xlsx)
    phases = convert_phases(xlsx)
    employees = convert_employees(xlsx)
    orders = convert_orders(xlsx, products)
    errors = convert_errors(xlsx)
    standard_times = convert_standard_times(xlsx, products, phases)
    allocations = convert_allocations(xlsx, employees)
    
    # Calculate OEE and Quality metrics
    oee_metrics = calculate_oee_metrics(xlsx)
    quality_analysis = calculate_quality_analysis(xlsx)
    
    # Generate dashboard stats with OEE data
    print("\n=== Generating Dashboard Stats ===\n")
    generate_dashboard_stats(products, employees, orders, errors, oee_metrics, quality_analysis)
    
    # Validate invariants
    validate_invariants(oee_metrics, quality_analysis, standard_times)
    
    print(f"\n✅ All files saved to: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
