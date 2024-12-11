import os
import sys
import subprocess
import pandas as pd
import seaborn as sns
import openai
import re
import json
from io import StringIO

# Function to extract metadata from the header comment block
def extract_metadata_from_file():
    """Extract the metadata block from the script's header."""
    header_pattern = re.compile(r"# ///.*?\n(.*?)\n# ///", re.DOTALL)
    with open(__file__, "r") as file:
        content = file.read()
    match = header_pattern.search(content)
    if not match:
        print("Error: Metadata not found in the header.")
        sys.exit(1)
    return match.group(1).strip()

# Function to parse metadata for required Python version and dependencies
def parse_metadata_block(metadata_block):
    """Parse the metadata block for Python version and dependencies."""
    required_version = None
    dependencies = []
    try:
        for line in metadata_block.splitlines():
            if "requires-python" in line:
                required_version = line.split("=")[1].strip().strip('"')
            elif "dependencies" in line:
                dependencies = eval(line.split("=")[1].strip())
    except Exception as e:
        print(f"Error parsing metadata: {e}")
        sys.exit(1)
    return required_version, dependencies

# Function to verify Python version
def check_python_version_requirements(min_version):
    """Ensure the current Python version meets the specified minimum version."""
    major, minor = map(int, min_version.split(".")[1:3])
    if sys.version_info < (major, minor):
        print(f"Error: Python {min_version} or higher is required.")
        sys.exit(1)

# Function to install dependencies from the metadata
def install_required_dependencies(packages):
    """Install the required dependencies using pip."""
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError as e:
            print(f"Error installing {package}: {e}")
            sys.exit(1)

# Function to find the file path in the directory or subdirectories
def search_file(filename, root_dir="."):
    """Search for a file within a directory and its subdirectories."""
    for root, _, files in os.walk(root_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None

# Function to load the dataset, handling encoding issues
def load_csv_file(file_path):
    """Load the CSV file with error handling for encoding."""
    try:
        data = pd.read_csv(file_path)
    except UnicodeDecodeError:
        print("Encoding error detected. Attempting conversion...")
        try:
            with open(file_path, "rb") as file:
                raw_data = file.read().decode("latin1")
            data = pd.read_csv(StringIO(raw_data))
        except Exception as e:
            print(f"Error in file conversion: {e}")
            sys.exit(1)
    print(f"Dataset loaded: {data.shape[0]} rows, {data.shape[1]} columns.")
    return data

# Function to perform basic data analysis (summary statistics and missing values)
def perform_basic_analysis(data):
    """Generate basic statistics and count missing values in the dataset."""
    try:
        stats = data.describe(include="all").transpose()
        missing_data = data.isnull().sum()
        return stats, missing_data
    except Exception as e:
        print(f"Error performing analysis: {e}")
        sys.exit(1)

# Function to generate visualizations from the dataset
def create_visualizations(data, output_directory):
    """Generate visualizations (heatmap, distribution, boxplot) for numeric columns."""
    visual_files = []
    try:
        numeric_columns = data.select_dtypes(include=["number"])
        if not numeric_columns.empty:
            # Generate a heatmap for correlations
            heatmap_file = os.path.join(output_directory, "correlation_heatmap.png")
            sns.heatmap(numeric_columns.corr(), annot=True, cmap="coolwarm", fmt=".2f")
            sns.pyplot.savefig(heatmap_file)
            sns.pyplot.close()
            visual_files.append(heatmap_file)

            # Generate a distribution plot for the first numeric column
            dist_file = os.path.join(output_directory, f"distribution_{numeric_columns.columns[0]}.png")
            sns.histplot(numeric_columns.iloc[:, 0], kde=True)
            sns.pyplot.savefig(dist_file)
            sns.pyplot.close()
            visual_files.append(dist_file)

            # Generate a box plot for the numeric data
            boxplot_file = os.path.join(output_directory, "boxplot_numeric_data.png")
            sns.boxplot(data=numeric_columns, orient="h")
            sns.pyplot.savefig(boxplot_file)
            sns.pyplot.close()
            visual_files.append(boxplot_file)
        else:
            print("No numeric data available for visualizations.")
    except Exception as e:
        print(f"Error generating visualizations: {e}")
    return visual_files

# Function to query the OpenAI API for summarizing the data
def query_openai_for_summary(prompt_text):
    """Query OpenAI's API to generate a summary of the dataset."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an expert data analyst."},
                      {"role": "user", "content": prompt_text}],
        )
        return response["choices"][0]["message"]["content"]
    except openai.OpenAIError as e:
        print(f"OpenAI API error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None

# Function to generate a detailed report based on data analysis
def generate_analysis_report(data, summary, missing_data, visuals):
    """Generate a comprehensive analysis report for the dataset."""
    try:
        column_info = json.dumps({col: str(dtype) for col, dtype in data.dtypes.items()}, indent=2)
        summary_text = summary.to_string()
        missing_text = missing_data.to_string()
        visuals_list = "\n".join(visuals)

        report_prompt = (
            "You are a highly skilled data scientist. Create a detailed and professional README.md file from the following dataset information. "
            "The report should highlight trends, insights, potential applications, and challenges. The summary should be clear, engaging, and accessible for all audiences.\n\n"
            "Dataset Columns and Types:\n" f"{column_info}\n\n" "Summary Statistics:\n" f"{summary_text}\n\n" 
            "Missing Data:\n" f"{missing_text}\n\n" "Visualizations:\n" f"{visuals_list}\n\n"
            "Write a structured and informative analysis with suggestions for next steps."
        )
        return query_openai_for_summary(report_prompt)
    except Exception as e:
        print(f"Error generating report: {e}")
        return None

# Function to write the analysis report to README.md
def write_report_to_file(story_text, visuals, output_path):
    """Write the analysis report and visualizations to a README.md file."""
    try:
        readme_path = os.path.join(output_path, "README.md")
        with open(readme_path, "w") as readme_file:
            readme_file.write("# Data Analysis Report\n\n")
            readme_file.write(story_text)
            readme_file.write("\n\n## Visualizations\n")
            for visual in visuals:
                readme_file.write(f"![{os.path.basename(visual)}]({os.path.basename(visual)})\n")
        print(f"README.md saved in {output_path}")
    except Exception as e:
        print(f"Error writing to README.md: {e}")

def main():
    """Main function to execute the entire analysis pipeline."""
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <dataset.csv>")
        sys.exit(1)

    file_name = sys.argv[1]
    dataset_path = search_file(file_name)

    if dataset_path is None:
        print(f"Error: File '{file_name}' not found.")
        sys.exit(1)

    print(f"Found dataset at: {dataset_path}")
    output_directory = os.path.dirname(dataset_path)
    data = load_csv_file(dataset_path)

    summary_stats, missing_values = perform_basic_analysis(data)
    generated_visuals = create_visualizations(data, output_directory)

    report_story = generate_analysis_report(data, summary_stats, missing_values, generated_visuals)
    if report_story:
        write_report_to_file(report_story, generated_visuals, output_directory)
        print("Analysis complete. README.md and visualizations generated.")
    else:
        print("Error generating report from OpenAI.")

if __name__ == "__main__":
    main()
