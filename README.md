# Amazon Ads Campaign Renaming Tool 📊

A powerful Streamlit application that automates the renaming of Amazon Advertising campaigns and ad groups based on performance data.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](your-app-url-here)

## 🎯 Features

- **Automatic Data Processing**: Upload your Amazon Ads bulk report and let the app analyze campaign performance
- **Smart Performance Analysis**: Automatically identifies best-performing ASINs, match types, and placements
- **Flexible Naming Schemes**: Build custom naming conventions with 7+ elements
- **Bulk Export**: Generate Amazon Ads-compatible bulk update files
- **Zero KPI Handling**: Intelligent fallback logic for campaigns with no conversions
- **Preview Before Export**: Review all changes before downloading

## 🚀 Live Demo

[Try it here](your-deployed-app-url) *(Add your Streamlit Cloud URL after deployment)*

## 📋 How It Works

### Step 1: Upload Your File
- Upload Amazon Ads bulk report (`.xlsx` format)
- App automatically finds and processes the Sponsored Products sheet
- Analyzes campaigns, ad groups, keywords, and placements

### Step 2: Build Your Naming Scheme
Choose from these elements:
- **Prefix**: Custom text (default: "SP")
- **Targeting Type**: A (Auto) or M (Manual)
- **Match Types**: Ex, Br, Ph, PAT, CAT (best performer highlighted with *)
- **Ad Group Count**: Number of ad groups (e.g., "3AdG")
- **Best ASIN**: Top-performing ASIN based on orders
- **Bidding Strategy**: Fix, UnD, DwnO
- **Best Placement**: TOS, PP, ROS

### Step 3: Preview Changes
- Paginated view of all campaigns
- Search by Campaign ID
- View old vs new names for campaigns and ad groups
- Check warnings and errors

### Step 4: Export
- Download bulk update file ready for Amazon Ads
- Upload directly to your Amazon Ads account

## 🛠️ Installation

### Local Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/amazon-ads-renamer.git
cd amazon-ads-renamer
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the app**
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## 📦 Requirements

- Python 3.8+
- streamlit >= 1.28.0
- pandas >= 2.0.0
- openpyxl >= 3.1.0

## 📊 Performance Ranking Logic

The app uses a sophisticated ranking system:

**Primary Ranking (for ASINs, Match Types, Placements):**
1. Orders (descending)
2. Conversion Rate (descending)
3. ROAS (descending)

**Zero KPI Fallback:**
1. Clicks (descending)
2. Impressions (descending)
3. Global ASIN performance (if still zero)

## 🎨 Example Naming Schemes

**Example 1: Standard Format**
```
SP-M-[Ex,*Br*,Ph]-B0ABCD1234-Fix-TOS
```
- Prefix: SP
- Targeting: Manual
- Match Types: Exact, Broad (best), Phrase
- ASIN: B0ABCD1234
- Bidding: Fixed
- Placement: Top of Search

**Example 2: Compact Format**
```
SP_A_B0XYZ9876_3AdG
```
- Prefix: SP
- Targeting: Auto
- ASIN: B0XYZ9876
- Ad Groups: 3

## 📝 File Structure

```
amazon-ads-renamer/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── .gitignore            # Git ignore file
└── assets/               # Screenshots and images (optional)
    └── screenshot.png
```

## 🔒 Privacy & Security

- **No data is stored**: All processing happens in your browser session
- **No external API calls**: Your Amazon Ads data never leaves your machine
- **Session-based**: Data is cleared when you close the browser

## 🐛 Troubleshooting

### "No Sponsored Products sheet found"
- Ensure your file is an Amazon Ads bulk report
- Check that Column A contains "Sponsored Products" entries

### "Campaign has no Product Ads"
- Some campaigns may be excluded if they have no product ads
- Check the error log in Step 3 for details

### Missing match types or placements
- If a campaign has no keyword/placement data, "N/A" will be used
- This is normal for brand new campaigns

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

Your Name
- GitHub: [@yourusername](https://github.com/yourusername)
- LinkedIn: [Your LinkedIn](https://linkedin.com/in/yourprofile)

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Designed for Amazon Advertising API bulk operations
- Inspired by the need for efficient campaign management

## 📞 Support

If you encounter any issues or have questions:
- Open an [Issue](https://github.com/yourusername/amazon-ads-renamer/issues)
- Check existing issues for solutions

---

**Note**: This tool is not affiliated with or endorsed by Amazon. It's an independent utility for managing Amazon Advertising campaigns.
