import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import sqlite3  # 导入 SQLite 库
import streamlit.config as st_config
import os
import webbrowser
import platform


# 创建数据库连接
conn = sqlite3.connect('病种数据.db')  # 创建或连接到 SQLite 数据库

# 使用侧边栏组织上传和搜索部分
with st.sidebar:
    tab1, tab2, tab3 = st.tabs(["病种", "病例", "耗材"])
    
    with tab1:
        selected_disease = None
        uploaded_file = st.file_uploader("上传病种详情文件(支持拖拽和文件选择)", type=["xlsx"])  # 支持拖拽和文件选择
        
        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file)
            df['耗材超标值（元）'] = pd.to_numeric(df['耗材超标值（元）'], errors='coerce')  # 保留之前的类型转换
            
            # 将数据写入数据库
            df.to_sql('病种详情', conn, if_exists='replace', index=False)  # 将 DataFrame 存储到数据库
            
            # 从数据库读取数据
            profit_loss_summary = pd.read_sql(
                'SELECT 名称, SUM(耗材超标值（元）) AS 耗材超标值, SUM(总例数) AS 总例数, MAX(DRG) AS DRG FROM 病种详情 GROUP BY 名称', 
                conn
            )
            top15_losses = profit_loss_summary.nlargest(15, '耗材超标值')
            
            # 添加搜索框
            search_query = st.text_input('搜索病种名称', placeholder='输入关键词搜索')
            
            if search_query:
                filtered_names = [name for name in profit_loss_summary['名称'].tolist() if search_query.lower() in name.lower()]
                selected_disease = st.selectbox('选择病种查看详情 (过滤后)', filtered_names)
            else:
                selected_disease = st.selectbox('选择病种查看详情', profit_loss_summary['名称'], placeholder='搜索病种名称...')
        else:
            st.write("请上传 Excel 文件以继续")


with tab2:
    
    # 添加文件上传组件
    uploaded_case_file = st.file_uploader("上传病例详情文件(支持拖拽和文件选择)", type=["xlsx"])  # 支持拖拽和文件选择
    
    if 'case_df' not in st.session_state and uploaded_case_file is not None:
        case_df = pd.read_excel(uploaded_case_file)  # 读取文件，如之前一样
        
        # 写入数据库（新添加）
        case_df.to_sql('病例详情', conn, if_exists='replace', index=False)  # 写入一个新表 '病例详情'
        
        # 现在从数据库读取并存储到 session state
        st.session_state.case_df = pd.read_sql('SELECT * FROM 病例详情', conn)  # 从数据库读取回来
        
        
    elif 'case_df' in st.session_state and uploaded_case_file is not None:
        # 如果已经在 session state 中，可以继续使用，但考虑从 DB 刷新
        case_df=st.session_state.case_df
    elif 'case_df' in st.session_state and uploaded_case_file is None: 
        del st.session_state['case_df']  # 释放旧的 case_df
        case_df=pd.DataFrame()#设置一个空数组来防止定义报错
        st.write("请上传 Excel 文件以继续") 
    else:
        st.write("请上传 Excel 文件以继续")

    
with tab3:
    
    uploaded_files = st.file_uploader("上传耗材使用文件(支持拖拽和文件选择)", type=["xlsx"], accept_multiple_files=True)  # 支持拖拽和文件选择
    #st.write(f"调试: uploaded_files 是 {uploaded_files} 和长度: {len(uploaded_files) if uploaded_files is not None else 'None'}")  # 添加这行
    #st.write(f"调试: 'combined_df' 在 session state 中吗? {'combined_df' in st.session_state}")
    

    if 'combined_df' not in st.session_state and uploaded_files is not None and len(uploaded_files) > 0:
        #st.write("调试: 进入了 if 块")  # 添加这行以确认
        all_dataframes = []  # 用于存储所有上传的 DataFrame
        for uploaded_filed in uploaded_files:
            all_sheets = pd.read_excel(uploaded_filed, sheet_name=None)  # 读取所有工作表
            for sheet, hdf in all_sheets.items():
                all_dataframes.append(hdf)  # 将每个工作表的 DataFrame 添加到列表中
        
        combined_df = pd.concat(all_dataframes, ignore_index=True)  # 合并所有 DataFrame
        
        # 写入数据库（新添加）
        combined_df.to_sql('耗材详情', conn, if_exists='replace', index=False)  # 将合并后的 DataFrame 写入数据库表 '耗材详情'
        
        # 现在从数据库读取并存储到 session state
        st.session_state.combined_df = pd.read_sql('SELECT * FROM 耗材详情', conn)  # 从数据库读取数据并更新 session state
    elif 'combined_df' in st.session_state and uploaded_files is not None and len(uploaded_files) > 0:
        combined_df = st.session_state.combined_df  # 如果已经在 session state 中，并且有文件上传，使用它
    elif 'combined_df' in st.session_state and uploaded_files is  not None and len(uploaded_files) == 0:  
        del st.session_state['combined_df']  # 如果没有上传文件，释放旧的 combined_df
        combined_df=pd.DataFrame()
        st.write("请上传 Excel 文件以继续")
    else:
        st.write("请上传 Excel 文件以继续")




# 主区域显示图表
main_tab1,main_tab2=st.tabs(["病种分析","病例分析"])#
with main_tab1:
    
    disease_tab1,disease_tab2=st.tabs(["病种盈亏数据","病种科室诊疗组数据"])
    with disease_tab1:
        if 'df' in locals():  # 确保文件已上传
            st.header('亏损病种图表（正为亏损）')  # 添加主标题
            # 显式确保 top15_losses 按 '耗材超标值' 降序排序
            top15_losses_sorted = top15_losses.sort_values(by='耗材超标值', ascending=False)
            fig = px.bar(
                top15_losses_sorted, 
                x='耗材超标值',
                y='名称', 
                orientation='h', 
                title='亏损最多的前15位病种的耗材超标值（元）',
                hover_data=['总例数'],
                category_orders={'名称': top15_losses_sorted['名称'].tolist()}  # 新添加：指定 y 轴顺序
            )
            st.plotly_chart(fig)
            
            #选择要额外显示的数量
            extra_num=st.selectbox(
                "选择要额外显示的数量",
                (15,30,45,60)
                
            )
            if extra_num is not None:
                next15_losses = profit_loss_summary.nlargest(75, '耗材超标值').tail(extra_num)  # 获取额外的盈亏病种
                next15_losses_sorted = next15_losses.sort_values(by='耗材超标值',ascending=False)#把耗材超标降序排列
                fig_more = px.bar(
                  next15_losses_sorted,
                  x='耗材超标值', 
                  y='名称', 
                  orientation='h',
                  height=30 *extra_num,
                  title='亏损最多的第16-45位病种的耗材超标值（元）',
                  hover_data=['总例数'],
                  category_orders={'名称': next15_losses_sorted['名称'].tolist()} 
                )
                st.plotly_chart(fig_more)
            
            # Add copyable and searchable name list below the chart

            names_list = profit_loss_summary['名称'].tolist()  #用所有名称来搜索

    with disease_tab2:
            st.subheader('病种合计均耗材分析 ')
            col1, col2 = st.columns(2)
            with col1:
                st.subheader('病种科室详情')
                if selected_disease:
                    disease_df = df[df['名称'] == selected_disease]
                    st.write(f'{selected_disease}')
                    st.write('')
                    st.write('')
                    # 显示饼状图
                    disease_details = disease_df.groupby('科室').agg(
                        合计耗材=('合计均耗材(元)', 'sum'),
                        总例数=('总例数', 'sum'),
                        耗材超标值=('耗材超标值（元）','sum'),                    DRG=('DRG', 'first'),
                    ).reset_index()
                    
                    # 饼状图显示逻辑
                    custom_data = np.stack((
                        disease_details['DRG'].values,
                        disease_details['耗材超标值'].values,
                        disease_details['总例数'].values
                    ), axis=-1)
                    
                    #绘制饼图
                    fig_detail = go.Figure(go.Pie(
                        labels=disease_details['科室'],
                        values=disease_details['合计耗材'],
                        customdata=custom_data,
                        hovertemplate=(
                            "%{percent}<br>"+
                            "科室: %{label}<br>" +
                            "总例数: %{customdata[0][2]}<br>" +
                            "DRG名称: %{customdata[0][0]}<br>" +
                            "盈亏情况: %{customdata[0][1]}<extra></extra>"
                        ),
                        marker=dict(colors=px.colors.diverging.RdYlGn),
                    ))
                    
                    fig_detail.update_layout(
                        title={
                            'text': f'{custom_data[0][0]} 的病种详情 总例数：{round(disease_details["总例数"].sum())}',
                            'x': 0.4,
                            'y': 0.97,
                            'xanchor': 'center',
                            'yanchor': 'top',
                        },
                        uniformtext_minsize=15,  # 文本信息最小值
                        uniformtext_mode='hide', # 3种模式：[False, 'hide', 'show']
                        
                    )
                    fig_detail.update_traces(
                        textposition='inside',
                        textinfo='percent+label',
                    
                    )
                    st.plotly_chart(fig_detail)         #绘制饼状图
                else:
                    st.write('请上传文件')


            with col2:
                st.subheader('病种诊疗组详情')
                if selected_disease:
                    # 选择科室查看详情
                    selected_department = st.selectbox('选择科室查看详情', disease_details['科室'], key='department_select')
                    
                    if selected_department:  # 确保选择了科室
                        department_details = disease_df[disease_df['科室'] == selected_department]
                        
                        if not department_details.empty and '诊疗组' in department_details.columns:
                            #以诊疗组来划分
                            group_details = department_details.groupby('诊疗组').agg(
                                合计耗材=('合计均耗材(元)', 'sum'),
                                总例数=('总例数', 'sum'),         
                                DRG=('DRG', 'first'),
                                耗材超标值=('耗材超标值（元）','sum'),
                            ).reset_index()
                            
                            
                                
                            depart_custom_data=np.stack((
                                group_details['DRG'].values,
                                group_details['耗材超标值'].values,
                                group_details['总例数'].values
                            ), axis=-1)


                            if not group_details.empty:
                                fig_treatment_detail = go.Figure(go.Pie(
                                    labels=group_details['诊疗组'],
                                    values=group_details['合计耗材'],
                                    customdata=depart_custom_data,
                                    hovertemplate=(
                                        "诊疗组: %{label}<br>" +
                                        "总例数: %{customdata[0][2]}<br>" +
                                        "DRG:%{customdata[0][0]}<br>"+

                                        "盈亏情况：%{customdata[0][1]}<br>"+
                                        "<extra></extra>"
                                    ),
                                    marker=dict(colors=px.colors.sequential.Viridis),  # 使用颜色方案
                                ))
                                
                                fig_treatment_detail.update_layout(
                                    title={
                                        'text': f'{selected_department} 的诊疗组详情',
                                        'x': 0.5,
                                        'y': 0.94,
                                        'xanchor': 'center',
                                        'yanchor': 'top'
                                    },
                                    uniformtext_minsize=15,  # 文本信息最小值
                                    uniformtext_mode='hide',  # 3种模式：[False, 'hide', 'show']
                                    transition_duration=500,  # 保持动画过渡
                                )
                                fig_treatment_detail.update_traces(
                                    textposition='inside',
                                    textinfo='percent+label',
                                    
                                )
                                st.plotly_chart(fig_treatment_detail)
                            else:
                                st.write("选定科室没有有效的诊疗组数据")
                        else:
                            st.write("选定科室数据不完整或缺少必要列")
            

            if st.button('病种数据的文字显示'):
                cost=np.stack((
                    disease_df['总费用（万元）'].sum(),
                    disease_df['DRG费用（万元）'].sum(),
                    disease_df['总例数'].sum(),
                    disease_df['医保实际费用（万元）'].sum(),
                    disease_df['合计均耗材(元)'].sum(),
                    disease_df['合计耗材横向参考(元)'].sum(),
                    disease_df['例均耗材横向参考（元）'].mean(),
                    disease_df['耗材超标值（元）'].sum(),
                ),axis=-1)

                # 新添加：计算每个诊疗组的 (总例数 * 平均住院天数) 然后求总和
                if '总例数' in disease_df.columns and '平均住院日（天）' in disease_df.columns:
                        disease_df['乘积总和'] = disease_df['总例数'] * disease_df['平均住院日（天）']  # 为每个组计算乘积
                        total_sum = disease_df['乘积总和'].sum()  # 对所有组求总和
                        #st.write(f"所有诊疗组的 (总例数 * 平均住院天数) 总和: {total_sum}")  # 显示结果
                average_days=total_sum/cost[2]
                st.write(f'平均住院日{round(average_days,2)}天，总费用{round(cost[0],2)}万元，DRG费用{round(cost[1],2)}万元,\
                医保实际费用{round(cost[3],2)}万元，支付率{round(cost[1]/cost[3]*100,2)}%')  # 显示总费用
                st.write(f'总例数{cost[2]}例，例均耗材{round(cost[4]/cost[2],2)}元，例均耗材横向参考{round(cost[6],2)}，耗材超标比{round(cost[4]/cost[5],2)},'+
                f'即每例亏损{round(cost[4]/cost[2]-cost[6],2)},总亏损{int(cost[7]//10000)}万{round(cost[7]%10000,2)}元'
                )
                
            
with main_tab2:
        sample_tab1,sample_tab2=st.tabs(["病例筛选","耗材使用"])#创建选项卡用于病例筛选、耗材使用
        
        with sample_tab1:
            if 'case_df' in st.session_state:
                case_df = st.session_state.case_df
                #选择病种

                if selected_disease:
                    case_DRG=case_df[case_df['DRG名称'] == selected_disease]   #显示某种病例的预测盈亏情况
                    columns =['DRG编码','姓名', '分类','出院科别','实际住院天数','预测盈亏','DRG名称']
                    st.subheader(f'{selected_disease}')
                    st.dataframe(case_DRG[columns],hide_index=True)         

                    # 选择病例
                    selected_case = st.selectbox('选择病例', case_DRG['姓名'])  # 假设病例名称在'病例名称'列
                    
                    
                    # 获取选定病例的分类和主要诊断
                    case_info = case_DRG[case_DRG['姓名'] == selected_case].iloc[0]
                    classification = case_info['分类']  # 分类在
                    primary_diagnosis = case_info['主要诊断名称']  # 主要诊断
                    symptoms_code=case_info['病案号']#转换为字符串
                    symptoms_code_numeric = pd.to_numeric(case_info['病案号'], errors='coerce')  # 转换为数字，处理无效值

                    # 筛选相同分类和主要诊断的病人
                    filtered_patients = case_DRG[
                        (case_DRG['分类'] == classification) & 
                        (case_DRG['主要诊断名称'] == primary_diagnosis)
                    ]
                    
                    # 找出住院天数相差不到3天的病人
                    selected_case_days = case_info['实际住院天数']  # 假设住院天数在'住院天数'列
                    similar_patients = filtered_patients[
                        (filtered_patients['实际住院天数'] >= selected_case_days - 4) & 
                        (filtered_patients['实际住院天数'] <= selected_case_days + 4)
                    ]
                    selected_similar_case=st.selectbox('选择相似病例以查看耗材使用',similar_patients['姓名'])
                    similar_case_info = case_DRG[case_DRG['姓名'] == selected_similar_case].iloc[0]
                    symptoms_similar_code=str(similar_case_info['病案号'])
                    symptoms_similar_numeric = pd.to_numeric(similar_case_info['病案号'], errors='coerce')  # 转换为数字，处理无效值
                    # 显示筛选结果
                    if not similar_patients.empty:
                        st.write("筛选出住院天数的相似病人：")
                        # 添加一列标记所选病人
                        similar_patients['是否选中'] = similar_patients['姓名'] == selected_case
                        
                        # 根据标记列进行排序，将所选病人放在第一位
                        similar_patients_sorted = similar_patients.sort_values(by='是否选中', ascending=False)

                        # 选择要显示的字段
                        selected_columns = ['病案号','姓名', '分类', '实际住院天数','出院科别','预测盈亏', '主要诊断名称','出院时间']
                        st.dataframe(similar_patients_sorted[selected_columns],hide_index=True)  # 只显示选定的字段
                    else:
                        st.write("没有找到相似的病人。")
            else:
                st.write('请上传病例文件以用于分析')

        with sample_tab2:
            
            
            
            if 'combined_df' in st.session_state and uploaded_files is not None and len(uploaded_files) > 0:
                
                sample_col1,sample_col2=st.columns(2)
                with sample_col1:
                    # 根据选择的病例过滤耗材使用数据
                    if selected_disease:
                        if selected_case:
                            st.subheader(f'病人{selected_case}的耗材使用')
                            filtered_data = combined_df[(combined_df['姓名'] == selected_case) &
                            (combined_df['住院号'] == symptoms_code)|
                            (pd.to_numeric(combined_df['门诊号'], errors='coerce') == symptoms_code_numeric)  # 转换并比较 '门诊号'
                            ].dropna(subset=['门诊号'])  # 去除转换失败的行
                            
                            
                            equip_columns = ['数量', 'AMT_HC', '医生姓名','项目名称']  # 更新列列表，包括新列
                            st.dataframe(filtered_data[equip_columns],hide_index=True)
                            #计算使用每种耗材使用总和
                            if not filtered_data.empty:
                                summary = filtered_data.groupby('项目代码').agg(
                                    数量=('数量', 'sum'),
                                    AMT_HC总和=('AMT_HC', 'sum'),
                                    使用医生=('医生姓名', 'first'),
                                    费用日期=('费用日期', 'first'),
                                    项目名称=('项目名称', 'first'),
                                    # 新添加：聚合新列
                                ).reset_index()
                                summary_columns = ['数量', 'AMT_HC总和', '使用医生','项目名称']
                                st.write("耗材使用统计结果：")
                                st.dataframe(summary[summary_columns],hide_index=True)
                            else:
                                st.write("未找到该病例的耗材使用数据。")
                with sample_col2:
                    if selected_disease:
                        if selected_similar_case:
                            st.subheader(f'病人{selected_similar_case}的耗材使用')
                            #st.write(f'{symptoms_similar_numeric}')

                            filtered_data = combined_df[(combined_df['姓名'] == selected_similar_case) &
                            (combined_df['住院号'] == symptoms_similar_code)|
                            (pd.to_numeric(combined_df['门诊号'], errors='coerce') == symptoms_similar_numeric)  # 转换并比较 '门诊号'
                            ].dropna(subset=['门诊号'])  # 去除转换失败的行
                            
                            
                            equip_columns = ['数量', 'AMT_HC', '医生姓名','项目名称']  # 更新列列表，包括新列
                            st.dataframe(filtered_data[equip_columns],hide_index=True)
                            #计算使用每种耗材使用总和
                            if not filtered_data.empty:
                                summary = filtered_data.groupby('项目代码').agg(
                                    数量=('数量', 'sum'),
                                    AMT_HC总和=('AMT_HC', 'sum'),
                                    使用医生=('医生姓名', 'first'),
                                    费用日期=('费用日期', 'first'),
                                    项目名称=('项目名称', 'first'),
                                    # 新添加：聚合新列
                                ).reset_index()
                                summary_columns = ['数量', 'AMT_HC总和', '使用医生','项目名称']
                                st.write("耗材使用统计结果：")
                                st.dataframe(summary[summary_columns],hide_index=True)
                            else:  
                                st.write("未找到该病例的耗材使用数据。")

            else:
                st.write('请上传耗材使用数据')

