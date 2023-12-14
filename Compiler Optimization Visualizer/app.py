from flask import Flask, render_template, request, jsonify
import re
import ast
import astor
app = Flask(__name__)


assignment_pattern = r'\b(\w+)\s*=\s*([-+]?\d*\.\d+|[-+]?\d+)\s*;'
usage_pattern = r'\b(\w+)\s*=\s*(\w+)\s*([+-/*%])\s*([-+]?\d*\.\d+|[-+]?\d+|[\w.]+)\s*;'
function_declaration_pattern = r'\b(\w+)\s+(\w+)\s*\([^)]*\)\s*{([^}]*)}'
function_call_pattern = r'\b(\w+)\s*\([^)]*\)\s*;'


standard_functions = ['printf', 'scanf', 'malloc', 'free', 'strlen', 'strcpy', 'strcat', 'strcmp', 'strncpy', 'strncat', 'strncmp']

def extract_variable_assignments(c_code):
    variable_assignments = {}
    used_variables = set()

    assignment_pattern = re.compile(r'\b(\w+)\s*=\s*([^;]+)\s*;')

    matches = assignment_pattern.findall(c_code)

    for match in matches:
        variable, value = match
        variable_assignments[variable] = value.strip()
        used_variables.add(variable)

    return variable_assignments, used_variables

def find_unused_variables(c_code):
    variable_pattern = re.compile(r'\b(?:int|char|float|double|long|short)\s+(\w+)\s*(?:=[^;]*)?;')
    variables = variable_pattern.findall(c_code)

    assignments, used_variables = extract_variable_assignments(c_code)

    unused_variables = [var for var in variables if var not in used_variables]

    return variables, unused_variables

def remove_unused_variables_from_code(c_code):
    variables, unused_variables = find_unused_variables(c_code)

    for var in unused_variables:
        c_code = re.sub(fr'\b(?:int|char|float|double|long|short)\s+{var}\s*(?:=[^;]*)?;', '', c_code)
        c_code = re.sub(fr'\b{var}\s*=\s*([^;]+)\s*;', '', c_code)

    return c_code
def find_new_additions(original_code, optimized_code):
    original_lines = set(original_code.split('\n'))
    optimized_lines = set(optimized_code.split('\n'))

    new_additions = optimized_lines - original_lines

    return new_additions

def detect_constant_propagation(code):
    updated_code = code  

    assignment_pattern = r'\b(\w+)\s*=\s*([-+]?\d*\.\d+|[-+]?\d+)\s*;'

    assignment_matches = re.findall(assignment_pattern, code)
    variable_values = dict(assignment_matches)

    for var, value in assignment_matches:
        updated_code = re.sub(rf'\b{var}\b', value, updated_code)

    return updated_code

    assignment_matches = re.findall(assignment_pattern, code)
    for var, value in assignment_matches:
        constant_values[var] = float(value)

    usage_matches = re.findall(usage_pattern, code)
    for var, left, op, right in usage_matches:
        if left in constant_values and right in constant_values:
            if op == '+':
                constant_values[var] = constant_values[left] + constant_values[right]
            elif op == '-':
                constant_values[var] = constant_values[left] - constant_values[right]
            elif op == '*':
                constant_values[var] = constant_values[left] * constant_values[right]
            elif op == '/':
                if constant_values[right] != 0:
                    constant_values[var] = constant_values[left] / constant_values[right]
                else:
                    constant_values.pop(var, None)

            updated_code = updated_code.replace(f"{var} = {left} {op} {right};", f"{var} = {constant_values[var]};")
    new_additions = find_new_additions(code, updated_code)
    return updated_code, new_additions 


def detect_inline_candidates(code):
    function_definitions = {}  
    function_calls_count = {}  

    function_declaration_pattern = r'\b(\w+)\s+(\w+)\s*\([^)]*\)\s*{([^}]*)}'
    function_matches = re.findall(function_declaration_pattern, code)
    for func_name, _, func_body in function_matches:
        function_definitions[func_name] = func_body

    function_call_pattern = r'\b(\w+)\s*\([^)]*\)\s*;'
    function_call_matches = re.findall(function_call_pattern, code)
    for func_name in function_call_matches:
        if func_name not in standard_functions:  
            function_calls_count[func_name] = function_calls_count.get(func_name, 0) + 1

    candidates_for_inlining = [func for func, count in function_calls_count.items() if count == 1]

    return function_definitions, candidates_for_inlining

def inline_functions(code, function_definitions, candidates_for_inlining):
    updated_code = code 
    comments = []

    for func_name in candidates_for_inlining:
        if func_name in function_definitions:
            func_call_pattern = re.compile(r'\b' + re.escape(func_name) + r'\s*\([^)]*\)\s*;')
            updated_code, count = func_call_pattern.subn(function_definitions[func_name], updated_code)
            
            if count > 0:
                comments.append(f'Inlined function: {func_name}')

    return updated_code, comments

def strength_reduction(code):
    code = re.sub(r'(\w+)\s*\*\s*2', r'\1 << 1', code)
    code = re.sub(r'(\w+)\s*\*\s*4', r'\1 << 2', code)
    code = re.sub(r'(\w+)\s*\*\s*8', r'\1 << 3', code)

    code = re.sub(r'(\w+)\s*/\s*2', r'\1 >> 1', code)
    code = re.sub(r'(\w+)\s*/\s*4', r'\1 >> 2', code)
    code = re.sub(r'(\w+)\s*/\s*8', r'\1 >> 3', code)

    return code

def highlight_lines(code, lines_to_highlight):
    highlighted_code = ""
    for i, line in enumerate(code.split('\n')):
        print(line)
        if line in lines_to_highlight:
            highlighted_code += f'<span class="highlight">{line}</span>\n'
        else:
            highlighted_code += f'{line}\n'
    return highlighted_code

class CSEVisitor(ast.NodeTransformer):
    def __init__(self):
        self.expr_dict = {}

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_var = node.targets[0].id

            if isinstance(node.value, ast.BinOp):
                expr_key = astor.to_source(node.value)
                if expr_key in self.expr_dict:
                    replacement_var = self.expr_dict[expr_key]
                    node.value = ast.Name(id=replacement_var, ctx=ast.Load())
                else:
                    temp_var = f"_temp_{len(self.expr_dict)}"
                    self.expr_dict[expr_key] = temp_var
                    node.targets.append(ast.Name(id=temp_var, ctx=ast.Store()))
            return node
        else:
            return self.generic_visit(node)

def evaluate_expression(expression):
    try:
        return str(eval(expression))
    except:
        return expression

def constant_folding(c_code):
    assignment_pattern = re.compile(r'(\w+)\s*=\s*([^;]+)\s*;')

    assignments = assignment_pattern.findall(c_code)

    for var, expression in assignments:
        constant_value = evaluate_expression(expression)
        c_code = c_code.replace(f'{var} = {expression};', f'{var} = {constant_value};')

    return c_code

def perform_cse(c_code):
    parsed_ast = ast.parse(c_code)

    cse_visitor = CSEVisitor()
    optimized_ast = cse_visitor.visit(parsed_ast)

    optimized_code = astor.to_source(optimized_ast)
    return optimized_code

@app.route('/')
def landing_page():
    return render_template('landingpage.html')

@app.route('/optimize', methods=['POST'])
def optimize():
    code_input = request.form['code_input']
    optimization_type = request.form['optimization_type']
    
    if optimization_type == 'Constant Propagation':
        updated_code = detect_constant_propagation(code_input)
        optimized_code = updated_code
        highlighted_code = find_new_additions(code_input, optimized_code)
        print(highlighted_code)
        comments = ['Constant Propagation Applied']

    elif optimization_type == 'Function Inlining':
        function_definitions, candidates_for_inlining = detect_inline_candidates(code_input)
        optimized_code, comments = inline_functions(code_input, function_definitions, candidates_for_inlining)
        highlighted_code = find_new_additions(code_input, optimized_code)
        comments = [candidates_for_inlining] if candidates_for_inlining else ["None"]


    elif optimization_type == 'Strength Reduction':
        updated_code = strength_reduction(code_input)
        optimized_code = updated_code
        highlighted_code = find_new_additions(code_input, optimized_code)
        comments = ['Strength Reduction Applied']
    elif optimization_type == 'Dead Code Elimination':
        updated_code = remove_unused_variables_from_code(code_input)
        optimized_code = updated_code
        highlighted_code = find_new_additions(code_input, optimized_code)
        comments = ['Dead Code Elimination Applied']
    elif optimization_type == 'Common Sub-Expression Elimination':
        updated_code = perform_cse(code_input)
        optimized_code = updated_code
        highlighted_code = find_new_additions(code_input, optimized_code)
        comments = ['Common Sub-Expression Elimination Applied']
    elif optimization_type == 'Constant Folding':
        updated_code = constant_folding(code_input)
        optimized_code = updated_code
        highlighted_code = find_new_additions(code_input, optimized_code)
        comments = ['Constant Folding Applied']
    else:
        return jsonify({'error': 'Invalid optimization type'})

    
    highlighted_code = highlight_lines(optimized_code, highlighted_code)

   
    return jsonify({'highlighted_code': highlighted_code, 'comments': comments})

if __name__ == '__main__':
    app.run(debug=True)
