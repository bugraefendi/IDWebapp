from flask import Flask, redirect, render_template, request, make_response,  url_for
from flask_bootstrap import Bootstrap
from flask import session 
from flask_session.__init__ import Session as FSession
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, IntegerField,  SelectField, BooleanField
from wtforms.validators import DataRequired, InputRequired
from sasctl import Session, current_session, get, post, put, delete
import pandas as pd
import plotly.graph_objects as go
import plotly
import json
from functools import wraps
import saspy
import time 
# Before you build the docker image please update the path of sascfg_personal.py at reason function.
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]}'
app.config['SESSION_TYPE'] = 'filesystem'
app.config.from_object(__name__)
FSession(app)
bootstrap = Bootstrap(app)


class SettingForms(FlaskForm):
    viya_url = StringField('Host name', validators=[DataRequired()])
    cas_host = StringField('What`s your CAS Host ?')
    username = StringField('SAS username',
                           validators=[DataRequired()])
    password = PasswordField('Password', validators=[InputRequired()])
    publishedDecision = StringField(
        'Decision Name', validators=[DataRequired()])


class Decisionform(FlaskForm):
    job = SelectField('Select your job', choices=[
                      ('Sales'), ('Manager'), ('Office'), ('Executive Professor'), ('Self'), ('Other')],default="")
    loan = IntegerField('How much Loan you need?')
    mortdue = IntegerField('Amount due on existing mortgage')
    delinq = IntegerField('No. of delinquent credit lines')
    derog = IntegerField('No. of major derogatory reports')
    clage = IntegerField('Age of  the oldest credit line (months)')
    ninq = IntegerField('No. of recent credit inquiries')
    clno = IntegerField('No. of credit lines')
    yoj = IntegerField('Years at present job')
    reason = SelectField('Why do you need credit?', choices=[
                         ('Debt Consolidation'), ('Home Improvement'), ('Other')])
    income = IntegerField('Current Income', validators=[DataRequired()])
    value = IntegerField('Current value of property')
    currentDebt = IntegerField('Current debt', validators=[DataRequired()])
    submit = SubmitField('Submit')
    average_active = BooleanField('Fill with average values', default=False)


# def login_required(f):
#     @wraps(f)
#     def wrap():
#         s = session.get('set')
#         if s == "SAS":
#             return redirect(url_for('scoreDecision'))
#         else:
#             return redirect(url_for('Login'))

#     return wrap


@app.route('/')
def home_page():
    return render_template('home.html')


@app.route('/viyatogo-singlenode/settings', methods=['GET', 'POST'])
def Login():
    global publishedDecision, form
    form = SettingForms()
    publishedDecision = form.publishedDecision.data

    if request.method == 'POST' and form.validate_on_submit:
        sess = Session(form.viya_url.data, form.username.data,
                       form.password.data, verify_ssl=False)
        current_session(sess)
        session['set'] = 'SAS'
        return redirect('/decision')
    else:
        redirect('404.html')
    return render_template('form.html', form=form)


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


def make_call(body):
    contentType = "application/vnd.sas.microanalytic.module.step.input+json"
    masExecutionResponse = post(f"microanalyticScore/modules/{publishedDecision}/steps/execute",
                                headers={"Content-Type": contentType}, data=json.dumps(body))
    if masExecutionResponse.get('executionState') == 'completed':
        resp = {d['name']: d['value']
                for d in dict(masExecutionResponse)['outputs'][1:18]}
        return resp
    elif masExecutionResponse.get('httpStatusCode') == 400:
        return make_response(masExecutionResponse.get('message'))
    else:
        return (masExecutionResponse.get('httpStatusCode'))


def get_model():
    global ModelDetail,InputVars,OutputVars
    headersDecisionID = {
        'Accept': 'application/vnd.sas.microanalytic.module+json',
        'If-Match': 'string',
        'If-Unmodified-Since': 'string'
    }
    decision_id = get(f'/microanalyticScore/modules/{publishedDecision}',
                  headers=headersDecisionID)
    decisionIDurl = decision_id.properties[0].get('value')
    headersModel = {
        'Accept': 'application/vnd.sas.decision+json'
    }
    decision_module = get(decisionIDurl, headers=headersModel)
    if decision_module.flow.steps[0].get('links')[0].get('rel') == 'model':

        modelID = decision_module.flow.steps[0].get('links')[0].get('href')
        headersModelID = {
            'Accept': 'application/vnd.sas.models.model+json'
        }
        a = get(modelID, headers=headersModelID)
        algo = a.get('algorithm')
        isChampion = a.get('candidateChampion')
        createdBy = a.get('createdBy')
        creationTime = a.get('creationTimeStamp')
        function = a.get('function')
        location = a.get('location')
        modelVersions = a.get('modelVersions')
        versionName = a.get('modelVersionName')
        modelName = a.get('name')
        fitstatDetails = a.get('fitStatUri')
        rocDetails = a.get('rocDataUri')
        liftDetails = a.get('liftDataUri')
        projectName = a.get('projectName')
        projectVersion = a.get('projectVersionNum')
        projectVersionName = a.get('projectVersionName')
        scoreCode = a.get('scoreCodeType')
        InputVars = a.modelTransformation.inputVariables
        OutputVars = a.modelTransformation.outputVariables



        ModelDetail = {
            'ModelName' : modelName,
            'ModelCreatedBy' : createdBy,
            'ModelCreationTime' : creationTime,
            'ModelFunction' : function,
            'ModelAlgorithm' : algo,
            'ModelScoreCodeType' : scoreCode,
            'ModelVersions' : modelVersions,
            'ModelVersionName' : versionName,
            'ModelLocation' : location,
            'ChampionModel' : isChampion,
            'ProjectName' : projectName,
            'ProjectVersion' : projectVersion,
            'ProjectVersionName': projectVersionName
            }
        return ModelDetail ,InputVars,OutputVars
    else:
        return('Cannot  find Model')



# This function finds the related decision`s id and calls the Decision macros to create reason plot for one observasion

def reason():
    global graphJson
    sas = saspy.SASsession(cfgfile=r'C:\Users\splbud\webapp-decision\sascfg_personal.py')
#/flasky/sascfg_personal.py
    reason_data = {"loan": formDecision.loan.data, "mortdue": formDecision.mortdue.data, "value": formDecision.value.data,
                   "reason": formDecision.reason.data, "job": formDecision.job.data, "yoj": formDecision.yoj.data, "derog": formDecision.derog.data,
                   "delinq": formDecision.delinq.data, "clage": formDecision.clage.data, "ninq": formDecision.ninq.data, "clno": formDecision.clno.data, "debtinc": debtinc}

    reason_data_pd = pd.DataFrame(reason_data, index=[0])
    sas.saslib('casuser', 'cas')
    requesthmeq = sas.df2sd(
        df=reason_data_pd, table='oneobs', libref='casuser')
    print(requesthmeq)

    # sas.submit('%DCM_GET_REVISIONS(TYPE=DECISION,TABLE=casuser.DECISIONID) ')
    # revs = sas.sasdata('DECISIONID', libref='casuser')
    # df = revs.to_df()
    # id = df.loc[0].iat[0]
    # ListDecision = id.split('/', 4)
    # DecisionId = '/' + ListDecision[1] + '/' + \
    #     ListDecision[2] + '/' + ListDecision[3]
    headers = {
  'Accept': 'application/vnd.sas.collection+json',
  'Accept-Item': 'application/vnd.sas.decision+json'
}

    f = get('/decisions/flows?name=hmeq',headers=headers)
    decisiontesid = '/decisions/flows/f90987a7-aaef-4a32-88cb-44a300980ed6'
    DecisionExecute = f' %DCM_EXECUTE_DECISION(uri ={decisiontesid},INPUTTABLE=casuser.oneobs,outputtable=casuser.execute)'
    sas_macro1 = sas.submit(DecisionExecute)
    sasmacro_2 = sas.submit(
        '%DCM_DECISION_PATH_FREQUENCY(INPUTTABLE=casuser.execute,outputtable=casuser.path);')
    sasmacro_3 = sas.submit(
        f'%DCM_decision_path_nodes(uri={decisiontesid},INPUTTABLE=casuser.path,outputtable=casuser.nodes)')
    df_nodes = sas.sasdata2dataframe('nodes', 'casuser')
    df_nodes_sorted = df_nodes.sort_values(by='node_seq_no')

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=10,
            line=dict(color="black", width=0.5),
            label=[df_nodes_sorted.loc[0].iat[5],
                   df_nodes_sorted.loc[1].iat[12],
                   df_nodes_sorted.loc[2].iat[12],
                   df_nodes_sorted.loc[3].iat[7]]
        ),
        link=dict(
            source=[0, 1, 2],
            target=[1, 2, 3],
            value=[1, 1, 1]
        ))])

    fig.update_layout(title_text="Decision Path ", font_size=10)
    fig.update_traces(orientation='h')
    graphJson = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJson


@app.route('/viyatogo-singlenode/decision', methods=['GET', 'POST'])
# @login_required
def scoreDecision():
    global formDecision, debtinc
    formDecision = Decisionform()

    res = {
        "inputs": [
            {"name": "JOB_",
                     "value": formDecision.job.data},
            {"name": "LOAN_",
                     "value": formDecision.loan.data},
            {"name": "MORTDUE_",
                     "value": formDecision.mortdue.data},
            {"name": "REASON_",
                     "value": formDecision.reason.data},
            {"name": "YOJ_",
                     "value": formDecision.yoj.data},
            {"name": "DEBTINC_",
                     "value": ''},
            {"name": "DELINQ_",
                     "value": formDecision.delinq.data},
            {"name": "DEROG_",
                     "value": formDecision.derog.data},
            {"name": "CLAGE_",
                     "value": formDecision.clage.data},
            {"name": "NINQ_",
                     "value": formDecision.delinq.data},
            {"name": "VALUE_",
                     "value": formDecision.value.data},
            {"name": "CLNO_",
                     "value": formDecision.clno.data}
        ]}
    if request.method == 'POST' and formDecision.validate_on_submit:
        debtinc = formDecision.currentDebt.data / formDecision.income.data
        res['inputs'][5] = {'name': 'DEBTINC_', 'value': debtinc}
        results = make_call(res)
        get_model()
        st = time.time()     
        reason()
        elapsed_time = time.time() - st
        print('Execution time:', time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
        return render_template('Results.html', results=results, graphJson=graphJson, ModelDetail = ModelDetail,InputVars=InputVars,OutputVars=OutputVars)

    return render_template('inputs.html', form=formDecision)


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
